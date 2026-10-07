"""Water Heater entity for Essency Water Heater integration."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_ECO,
    STATE_PERFORMANCE,
    STATE_ELECTRIC,
    STATE_OFF,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    HEAT_MODE_OFF,
    HEAT_MODE_SAVER,
    HEAT_MODE_STANDARD,
    HEAT_MODE_BOOST,
    HEAT_MODE_VACATION,
)
from .coordinator import EssencyDataUpdateCoordinator
from .entity import EssencyEntity

_LOGGER = logging.getLogger(__name__)

HA_TO_ESSENCY_MODE = {
    STATE_OFF: HEAT_MODE_OFF,
    STATE_ECO: HEAT_MODE_SAVER,
    STATE_ELECTRIC: HEAT_MODE_STANDARD,
    STATE_PERFORMANCE: HEAT_MODE_BOOST,
}

ESSENCY_TO_HA_MODE = {
    HEAT_MODE_OFF: STATE_OFF,
    HEAT_MODE_SAVER: STATE_ECO,
    HEAT_MODE_STANDARD: STATE_ELECTRIC,
    HEAT_MODE_BOOST: STATE_PERFORMANCE,
    HEAT_MODE_VACATION: STATE_ECO,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Essency water heater entity."""
    coordinator: EssencyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EssencyWaterHeater(coordinator)])


class EssencyWaterHeater(EssencyEntity, WaterHeaterEntity):
    """Essency Water Heater Entity."""

    _attr_name = None  # Uses device name
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
    )

    def __init__(self, coordinator: EssencyDataUpdateCoordinator) -> None:
        """Initialize the water heater entity."""
        super().__init__(coordinator, key="water_heater")
        self._attr_operation_list = [
            STATE_ELECTRIC,
            STATE_ECO,
            STATE_PERFORMANCE,
            STATE_OFF,
        ]
        self._attr_min_temp = 110.0
        self._attr_max_temp = 140.0

        # Optimistic state tracking
        self._optimistic_op_mode: str | None = None
        self._optimistic_op_until: float = 0.0
        self._optimistic_away: bool | None = None
        self._optimistic_away_until: float = 0.0
        self._optimistic_temp: float | None = None
        self._optimistic_temp_until: float = 0.0

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        unit = self.attributes.get("csoTempSetUnit", "F")
        return UnitOfTemperature.FAHRENHEIT if unit == "F" else UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        hw_target = self.attributes.get("csoTempSetValue")
        hw_val = float(hw_target) if hw_target is not None else None

        if self._optimistic_temp is not None:
            if time.time() < self._optimistic_temp_until:
                if hw_val is not None and abs(hw_val - self._optimistic_temp) < 0.1:
                    self._optimistic_temp = None
                    return hw_val
                return self._optimistic_temp
            self._optimistic_temp = None

        return hw_val

    @property
    def current_temperature(self) -> float | None:
        """Return current estimated water temperature."""
        # When hot water level is full (100%), temperature equals target
        level = self.attributes.get("csoHotWaterLevel")
        target = self.target_temperature
        if target is not None and level is not None:
            # Estimate temperature based on available capacity
            # 100% capacity = target temp; drops toward baseline 60F if depleted
            est = 60.0 + ((target - 60.0) * (level / 100.0))
            return round(est, 1)
        return target

    @property
    def current_operation(self) -> str | None:
        """Return current operation mode."""
        hw_mode = self.attributes.get("csmHeatMode")
        if hw_mode is None:
            hw_mode = self.attributes.get("shmHeatMode")
        hw_ha_mode = ESSENCY_TO_HA_MODE.get(hw_mode, STATE_UNKNOWN)

        if self._optimistic_op_mode is not None:
            if time.time() < self._optimistic_op_until:
                if hw_ha_mode == self._optimistic_op_mode:
                    self._optimistic_op_mode = None
                    return hw_ha_mode
                return self._optimistic_op_mode
            self._optimistic_op_mode = None

        return hw_ha_mode

    @property
    def is_away_mode_on(self) -> bool:
        """Return true if away/vacation mode is active."""
        hw_vac = int(self.attributes.get("csmVacationStatus", 0) or 0) > 0

        if self._optimistic_away is not None:
            if time.time() < self._optimistic_away_until:
                if hw_vac == self._optimistic_away:
                    self._optimistic_away = None
                    return hw_vac
                return self._optimistic_away
            self._optimistic_away = None

        return hw_vac

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is not None:
            self._optimistic_temp = float(temperature)
            self._optimistic_temp_until = time.time() + 25.0
            self.async_write_ha_state()

            try:
                await self.coordinator.api.async_set_temperature(
                    self.coordinator.device_id, temperature
                )
            except Exception:
                self._optimistic_temp = None
                self._optimistic_temp_until = 0.0
                self.async_write_ha_state()
                raise

            self.hass.async_create_task(self._async_poll_confirmation())

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        mode_val = HA_TO_ESSENCY_MODE.get(operation_mode)
        if mode_val is not None:
            self._optimistic_op_mode = operation_mode
            self._optimistic_op_until = time.time() + 25.0
            self.async_write_ha_state()

            try:
                await self.coordinator.api.async_set_heat_mode(
                    self.coordinator.device_id, mode_val
                )
            except Exception:
                self._optimistic_op_mode = None
                self._optimistic_op_until = 0.0
                self.async_write_ha_state()
                raise

            self.hass.async_create_task(self._async_poll_confirmation())

    async def async_set_away_mode(self, away_mode: bool) -> None:
        """Turn away/vacation mode on or off."""
        self._optimistic_away = away_mode
        self._optimistic_away_until = time.time() + 25.0
        self.async_write_ha_state()

        try:
            await self.coordinator.api.async_set_vacation(
                self.coordinator.device_id, enable=away_mode
            )
        except Exception:
            self._optimistic_away = None
            self._optimistic_away_until = 0.0
            self.async_write_ha_state()
            raise

        self.hass.async_create_task(self._async_poll_confirmation())

    async def _async_poll_confirmation(self) -> None:
        """Poll coordinator at intervals to confirm state update."""
        for delay in (2.0, 3.0, 5.0):
            await asyncio.sleep(delay)
            if (
                self._optimistic_temp is None
                and self._optimistic_op_mode is None
                and self._optimistic_away is None
            ):
                break
            await self.coordinator.async_request_refresh()
