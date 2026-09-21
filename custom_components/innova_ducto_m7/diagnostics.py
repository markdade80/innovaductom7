"""Diagnostics without account secrets, MAC, home ID or device name."""
from . import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        return {"configured": True, "state": str(entry.state)}
    return {"protocol": "Innova cloud v2 / APK 3.1.3", "last_update_success": coordinator.last_update_success,
            "device_uid": coordinator.client.device.get("uid"), "node_id": coordinator.client.node,
            "state": coordinator.data}
