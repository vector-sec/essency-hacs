"""Number platform for Essency Water Heater integration."""

from __future__ import annotations

import logging
from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEFAULT_SAVER_DURATION
from .coordinator import EssencyDataUpdateCoordinator
from .entity import EssencyEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Essency number entities."""
    coordinator: EssencyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EssencyWaterSaverDurationNumber(coordinator)])


class EssencyWaterSaverDurationNumber(EssencyEntity, RestoreNumber):
    """Configurable duration for Water Saver mode."""

    _attr_name = "Water Saver Duration"
    _attr_icon = "mdi:timer-outline"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 1.0
    _attr_native_max_value = 30.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: EssencyDataUpdateCoordinator) -> None:
        """Initialize water saver duration number entity."""
        super().__init__(coordinator, key="water_saver_duration")
        self._current_value: float = float(coordinator.water_saver_duration)

    async def async_added_to_hass(self) -> None:
        """Restore previous state on startup."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data and last_data.native_value is not None:
            self._current_value = float(last_data.native_value)
            self.coordinator.water_saver_duration = int(self._current_value)
        else:
            self._current_value = float(self.coordinator.water_saver_duration)

    @property
    def native_value(self) -> float:
        """Return the current duration setting in minutes."""
        return float(self.coordinator.water_saver_duration)

    async def async_set_native_value(self, value: float) -> None:
        """Update the duration in minutes."""
        int_val = int(round(value))
        self._current_value = float(int_val)
        self.coordinator.water_saver_duration = int_val
        self.async_write_ha_state()
        _LOGGER.debug("Updated Essency Water Saver duration to %d minutes", int_val)
