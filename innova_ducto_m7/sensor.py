"""Humidity reported by Innova M7/fan coil."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Humidity(hass.data[DOMAIN][entry.entry_id], entry)])


class Humidity(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Umidità"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = entry.unique_id + "_humidity"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.unique_id)}}

    @property
    def native_value(self):
        value = self.coordinator.data.get("humidity")
        return round(value, 1) if value is not None else None
