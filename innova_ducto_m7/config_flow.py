"""Login and device selection for Innova cloud v2."""
import logging
import re
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers import selector
from .api import Client, ApiError, norm
from . import DOMAIN

LOGGER = logging.getLogger(__name__)


class InnovaFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = dict(user_input)
            data["email"] = data["email"].strip()
            mac = norm(data["mac"].strip())
            if not re.fullmatch(r"[0-9a-f]{12}", mac):
                errors["base"] = "invalid_mac"
            else:
                data["mac"] = ":".join(mac[i:i+2] for i in range(0, 12, 2)).upper()
                client = Client(data["email"], data["password"], data["mac"], data.get("node_id"))
                try:
                    await client.login()
                except Exception as err:
                    detail = str(err) if isinstance(err, ApiError) else type(err).__name__
                    LOGGER.error("Innova v2 configuration: %s", detail)
                    errors["base"] = "cannot_connect"
                else:
                    data["node_id"] = client.node
                    await self.async_set_unique_id(f"{mac}_{client.node}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=client.device.get("name") or "Innova Ducto M7", data=data)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("email"): str,
            vol.Required("password"): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Required("mac"): str,
            vol.Optional("node_id"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        }), errors=errors)
