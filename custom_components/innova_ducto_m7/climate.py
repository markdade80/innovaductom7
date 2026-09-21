"""Fan coil and M7 thermostat controls."""
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError
from . import DOMAIN

MODES = {1: HVACMode.AUTO, 2: HVACMode.HEAT, 3: HVACMode.COOL, 4: HVACMode.DRY, 5: HVACMode.FAN_ONLY}
FANS = {5: "Turbo", 4: "Max", 3: "Medio", 2: "Min", 1: "Auto"}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([InnovaClimate(hass.data[DOMAIN][entry.entry_id], entry)])


class InnovaClimate(CoordinatorEntity, ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
                                | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
                                | ClimateEntityFeature.PRESET_MODE)
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.unique_id)}, "manufacturer": "Innova",
                                  "name": entry.title, "model": "Ducto / M7 (cloud v2)"}

    @property
    def current_temperature(self):
        return self.coordinator.data.get("temperature")

    @property
    def current_humidity(self):
        return self.coordinator.data.get("humidity")

    @property
    def target_temperature(self):
        return self.coordinator.data.get("target")

    @property
    def min_temp(self):
        return self.coordinator.data.get("min", 5)

    @property
    def max_temp(self):
        return self.coordinator.data.get("max", 35)

    @property
    def target_temperature_step(self):
        return self.coordinator.data.get("step", 0.5)

    @property
    def hvac_mode(self):
        return MODES.get(self.coordinator.data.get("mode")) if self.coordinator.data.get("power") else HVACMode.OFF

    @property
    def hvac_modes(self):
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.FAN_ONLY, HVACMode.AUTO]

    @property
    def fan_mode(self):
        return FANS.get(self.coordinator.data.get("fan"))

    @property
    def fan_modes(self):
        return list(FANS.values())

    @property
    def preset_mode(self):
        return self.coordinator.data.get("preset")

    @property
    def preset_modes(self):
        return ["Manuale", "Calendario"]

    async def async_set_preset_mode(self, preset_mode):
        try:
            await self.coordinator.client.set_preset(preset_mode)
        except Exception as err:
            raise HomeAssistantError("Impossibile cambiare la programmazione Innova") from err
        await self.coordinator.async_request_refresh()

    async def send(self, **kwargs):
        try:
            await self.coordinator.client.set_state(**kwargs)
        except Exception as err:
            raise HomeAssistantError("Innova command failed; check cloud connectivity") from err
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs[ATTR_TEMPERATURE]
        if not self.min_temp <= temperature <= self.max_temp:
            raise HomeAssistantError("Temperatura fuori dai limiti del dispositivo")
        if self.preset_mode != "Manuale":
            await self.async_set_preset_mode("Manuale")
            if not self.coordinator.last_update_success or self.preset_mode != "Manuale":
                raise HomeAssistantError("Passaggio a Manuale non ancora confermato; riprova tra qualche secondo")
        await self.send(target=kwargs[ATTR_TEMPERATURE])

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self.send(power=False)
        else:
            await self.send(power=True, mode=next(k for k, v in MODES.items() if v == hvac_mode))

    async def async_set_fan_mode(self, fan_mode):
        await self.send(fan=next(k for k, v in FANS.items() if v == fan_mode))

    async def async_turn_on(self):
        await self.send(power=True)

    async def async_turn_off(self):
        await self.send(power=False)
