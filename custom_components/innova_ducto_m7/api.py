"""Innova app 3.1.3 REST and protobuf protocol, reconstructed from APK."""
import asyncio
import logging
import math
import socket
import ssl
import struct
import time
import uuid

import aiohttp
import h2.config
import h2.connection
import h2.events

LOGGER = logging.getLogger(__name__)
BASE = "https://v2.api.innova.solutiontech.tech/app"
HOST = "v2.grpc.innova.solutiontech.tech"
SERVICE = "/services.app.AppService/"


class ApiError(Exception):
    """A sanitized cloud error."""


def varint(value):
    if value < 0:
        raise ValueError("Negative varint")
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    return bytes(out) + bytes([value])


def integer(field, value):
    return varint(field << 3) + varint(value)


def message(field, value):
    return varint((field << 3) | 2) + varint(len(value)) + value


def floating(field, value):
    if not math.isfinite(value):
        raise ValueError("Nonfinite value")
    return varint((field << 3) | 5) + struct.pack("<f", value)


def fields(data, repeated=False):
    pos = 0
    result = {}

    def readvar():
        nonlocal pos
        value = 0
        for shift in range(0, 70, 7):
            if pos >= len(data):
                raise ApiError("Truncated protobuf")
            b = data[pos]
            pos += 1
            value |= (b & 127) << shift
            if not b & 128:
                return value
        raise ApiError("Invalid protobuf varint")

    while pos < len(data):
        tag = readvar()
        num, wire = tag >> 3, tag & 7
        if not num:
            raise ApiError("Invalid protobuf field")
        if wire == 0:
            value = readvar()
        elif wire in (1, 2, 5):
            length = readvar() if wire == 2 else (8 if wire == 1 else 4)
            if pos + length > len(data):
                raise ApiError("Truncated protobuf field")
            value = data[pos:pos + length]
            pos += length
            if wire == 5:
                value = struct.unpack("<f", value)[0]
        else:
            raise ApiError("Unsupported protobuf wire type")
        if repeated:
            result.setdefault(num, []).append(value)
        else:
            result[num] = value
    return result


def norm(mac):
    return mac.replace(":", "").replace("-", "").lower()


def check_response(payload):
    top = fields(payload)
    if 1 in top:
        error = fields(top[1])
        raise ApiError(f"Device response error code {error.get(1, 0)}")
    return top


def decode_snapshot(payload, node):
    top = check_response(payload)
    device = fields(top.get(2, b""))
    shared = fields(device.get(1, b""))
    state = fields(shared.get(1, b""), repeated=True)
    for encoded in state.get(2, []):
        entry = fields(encoded)
        if entry.get(1, 0) != node:
            continue
        value = fields(entry.get(2, b""))
        family = 2 if 2 in value else (3 if 3 in value else None)
        if family is None:
            raise ApiError(f"Unsupported node state fields: {sorted(value)}")
        raw = fields(value[family])
        result = {"family": "fancoil" if family == 2 else "thermostat",
                  "power": bool(raw.get(2, 0)), "alarms": raw.get(1, 0)}
        if 9 in raw:
            result["preset"] = {1: "Calendario", 2: "Manuale", 3: "Antigelo"}.get(fields(raw[9]).get(1, 0))
        for num, key in ((7, "temperature"), (8, "humidity"), (6, "swing")):
            if num in raw:
                result[key] = raw[num]
        for num, key in ((4, "mode"), (5, "fan")):
            if num in raw:
                result[key] = fields(raw[num]).get(1, 0)
        if 3 in raw:
            sp = fields(raw[3])
            for num, key in ((1, "target"), (2, "min"), (3, "max"), (4, "step")):
                if num in sp:
                    result[key] = sp[num]
        return result
    raise ApiError(f"Node {node} absent from full-state response (top fields {sorted(top)})")


def decode_event(payload, mac, node):
    envelope = fields(payload)
    if 1 not in envelope:
        return None
    device = fields(envelope[1])
    if device.get(1) != bytes.fromhex(norm(mac)) or device.get(2, 0) != node:
        return None
    event = fields(device.get(3, b""))
    if 3 not in event:
        return None
    state = fields(event[3])
    family = 3 if 3 in state else (5 if 5 in state else None)
    if family is None:
        raise ApiError("Device returned unsupported state family: " + str(sorted(state)))
    raw = fields(state[family])
    result = {"family": "fancoil" if family == 3 else "thermostat"}
    for num, key in ((1, "alarms"), (2, "power"), (4, "temperature"),
                     (5, "mode"), (6, "fan"), (7, "swing"), (9, "humidity")):
        if num in raw:
            result[key] = raw[num]
    if 3 in raw:
        sp = fields(raw[3])
        for num, key in ((1, "target"), (2, "min"), (3, "max"), (4, "step")):
            if num in sp:
                result[key] = sp[num]
    return result


class Client:
    def __init__(self, email, password, mac, node=None):
        self.email, self.password, self.mac = email, password, mac
        self.node = node
        self.token = None
        self.home = None
        self.device = {}
        self.state = {}

    async def login(self):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
            async with session.post(BASE + "/users/login", json={"email": self.email, "password": self.password}) as response:
                if response.status != 200:
                    raise ApiError(f"Login HTTP {response.status}")
                data = await response.json()
            self.token = data.get("token")
            if not isinstance(self.token, str) or not self.token:
                raise ApiError("Login response missing token")
            async with session.get(BASE + "/homes", headers={"Authorization": "Bearer " + self.token}) as response:
                if response.status != 200:
                    raise ApiError(f"Homes HTTP {response.status}")
                homes = await response.json()
        if not isinstance(homes, list):
            raise ApiError("Unexpected homes response structure")
        matches = [(h, d) for h in homes for d in h.get("devices", [])
                   if norm(d.get("macAddress", "")) == norm(self.mac)
                   and (self.node is None or d.get("nodeId", 0) == self.node)]
        if not matches:
            raise ApiError("MAC/node not found among account devices")
        if len(matches) != 1:
            raise ApiError("Multiple nodes for this MAC; specify node_id in configuration")
        home, self.device = matches[0]
        self.home = uuid.UUID(home["id"]).bytes
        self.node = self.device.get("nodeId", 0)
        LOGGER.warning("Innova v2 discovery OK: node=%s, uid=%s", self.node, self.device.get("uid"))

    def request(self, body):
        return message(1, bytes.fromhex(norm(self.mac))) + integer(2, self.node) + message(3, body)

    def exchange(self, command=None):
        """Read the full node snapshot from the SendDevice unary response."""
        reading = command is None
        request = message(2, message(1, b"")) if reading else command
        payload = self.request(request)
        # The official app requests all nodes through node 0.
        if reading:
            payload = message(1, bytes.fromhex(norm(self.mac))) + integer(2, 0) + message(3, request)
        ctx = ssl.create_default_context()
        ctx.set_alpn_protocols(["h2"])
        conn = h2.connection.H2Connection(config=h2.config.H2Configuration(header_encoding="utf-8"))
        buf = bytearray()
        replies = []
        status = None
        deadline = time.monotonic() + 25
        with socket.create_connection((HOST, 443), timeout=10) as raw:
            with ctx.wrap_socket(raw, server_hostname=HOST) as sock:
                sock.settimeout(3)
                conn.initiate_connection()
                sid = conn.get_next_available_stream_id()
                conn.send_headers(sid, [(":method", "POST"), (":scheme", "https"),
                    (":authority", HOST), (":path", SERVICE + "SendDevice"),
                    ("content-type", "application/grpc"), ("te", "trailers"),
                    ("authorization", "Bearer " + self.token)])
                conn.send_data(sid, struct.pack(">BI", 0, len(payload)) + payload, end_stream=True)
                sock.sendall(conn.data_to_send())
                while time.monotonic() < deadline:
                    try:
                        chunk = sock.recv(65535)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    ended = False
                    for event in conn.receive_data(chunk):
                        if isinstance(event, (h2.events.ResponseReceived, h2.events.TrailersReceived)):
                            headers = dict(event.headers)
                            if headers.get(":status", "200") != "200":
                                raise ApiError("gRPC HTTP " + headers[":status"])
                            if "grpc-status" in headers:
                                status = headers["grpc-status"]
                                if status != "0":
                                    raise ApiError("gRPC status " + status)
                        elif isinstance(event, h2.events.DataReceived):
                            conn.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
                            buf.extend(event.data)
                            if len(buf) > 4 * 1024 * 1024:
                                raise ApiError("Oversized response")
                            while len(buf) >= 5:
                                compressed, length = struct.unpack(">BI", buf[:5])
                                if compressed or length > 4 * 1024 * 1024:
                                    raise ApiError("Unsupported gRPC frame")
                                if len(buf) < 5 + length:
                                    break
                                replies.append(bytes(buf[5:5+length]))
                                del buf[:5+length]
                        elif isinstance(event, h2.events.StreamEnded):
                            ended = True
                        elif isinstance(event, (h2.events.StreamReset, h2.events.ConnectionTerminated)):
                            raise ApiError("gRPC stream closed unexpectedly")
                    sock.sendall(conn.data_to_send())
                    if ended:
                        if status != "0" or buf or len(replies) != 1:
                            raise ApiError("Incomplete unary reply")
                        if reading:
                            result = decode_snapshot(replies[0], self.node)
                            LOGGER.debug("Innova full state decoded: family=%s fields=%s", result["family"], sorted(result))
                            return result
                        check_response(replies[0])
                        return None
        raise ApiError("SendDevice response timeout")

    async def update(self):
        if not self.token:
            await self.login()
        try:
            result = await asyncio.to_thread(self.exchange)
        except ApiError as err:
            if str(err) == "gRPC status 16":
                await self.login()
                result = await asyncio.to_thread(self.exchange)
            else:
                raise
        self.state.update(result)
        return dict(self.state)

    async def set_preset(self, preset):
        """Toggle the node's manual override exactly as APK sa1/ra1 do."""
        if preset not in ("Manuale", "Calendario"):
            raise ApiError("Unsupported preset")
        if self.state.get("family") not in ("fancoil", "thermostat"):
            raise ApiError("Read a supported device state before sending commands")
        enabled = preset == "Manuale"
        config = integer(1, int(enabled))
        if not enabled:
            config += message(2, integer(1, 0))
        # shared(2).set_operation_mode(3).manual(2).nodes(1)[node] = config.
        node_entry = integer(1, self.node) + message(2, config)
        command = message(2, message(3, message(2, message(1, node_entry))))
        await asyncio.to_thread(self.exchange, command)

    async def set_state(self, *, power=None, target=None, mode=None, fan=None):
        family = self.state.get("family")
        if family not in ("fancoil", "thermostat"):
            raise ApiError("Read a supported device state before sending commands")
        payload = b""
        if power is not None:
            payload += integer(1, int(power))
        if target is not None:
            if not self.state.get("min", 5) <= target <= self.state.get("max", 35):
                raise ApiError("Temperature outside device limits")
            payload += floating(2, target)
        if mode is not None:
            if mode not in (1, 2, 3, 4, 5):
                raise ApiError("Invalid mode")
            payload += integer(3, mode)
        if fan is not None:
            if fan not in (1, 2, 3, 4, 5):
                raise ApiError("Invalid fan speed")
            payload += integer(4, fan)
        await asyncio.to_thread(self.exchange, message(5 if family == "fancoil" else 6, message(1, payload)))
