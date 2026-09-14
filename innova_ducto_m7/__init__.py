"""Innova Ducto/M7 cloud v2 integration."""
from datetime import timedelta
import logging
from homeassistant.const import Platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import Client

DOMAIN = "innova_ducto_m7"
LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    client = Client(entry.data["email"], entry.data["password"], entry.data["mac"], entry.data.get("node_id"))

    async def update():
        try:
            return await client.update()
        except Exception as err:
            # Do not log response bodies or credentials.
            detail = str(err) if err.__class__.__name__ == "ApiError" else type(err).__name__
            raise UpdateFailed(detail) from None

    coordinator = DataUpdateCoordinator(hass, LOGGER, name="Innova Ducto M7", update_method=update,
                                        update_interval=timedelta(seconds=60))
    coordinator.client = client
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.CLIMATE, Platform.SENSOR])
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, [Platform.CLIMATE, Platform.SENSOR]):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False
