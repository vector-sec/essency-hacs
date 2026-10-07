"""Sensor platform for Essency Water Heater integration."""

from __future__ import annotations

import logging
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HEAT_MODE_MAP
from .coordinator import EssencyDataUpdateCoordinator
from .entity import EssencyEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EssencySensorEntityDescription(SensorEntityDescription):
    """Describes Essency sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSOR_DESCRIPTIONS: tuple[EssencySensorEntityDescription, ...] = (
    EssencySensorEntityDescription(
        key="hot_water_level",
        name="Hot Water Available",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("attributes", {}).get("csoHotWaterLevel"),
    ),
    EssencySensorEntityDescription(
        key="target_temperature",
        name="Target Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("attributes", {}).get("csoTempSetValue"),
    ),
    EssencySensorEntityDescription(
        key="power",
        name="Estimated Power",
        icon="mdi:flash",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("power_w", 0.0),
    ),
    EssencySensorEntityDescription(
        key="heat_mode",
        name="Operating Mode",
        icon="mdi:tune-vertical",
        value_fn=lambda data: HEAT_MODE_MAP.get(
            data.get("attributes", {}).get("csmHeatMode"), "Unknown"
        ),
    ),
    EssencySensorEntityDescription(
        key="heat_source",
        name="Heat Source Status",
        icon="mdi:radiator",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: "Heating (4.5 kW)" if data.get("is_heating") else "Idle",
    ),
    EssencySensorEntityDescription(
        key="boost_counter",
        name="Boost Cycles Counter",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            int(data.get("telemetry", {}).get("BOOST_COUNTER"))
            if data.get("telemetry", {}).get("BOOST_COUNTER") is not None
            else None
        ),
    ),
    EssencySensorEntityDescription(
        key="vacation_counter",
        name="Vacation Cycles Counter",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            int(data.get("telemetry", {}).get("VACATION_COUNTER"))
            if data.get("telemetry", {}).get("VACATION_COUNTER") is not None
            else None
        ),
    ),
    EssencySensorEntityDescription(
        key="saver_counter",
        name="Saver Cycles Counter",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            int(data.get("telemetry", {}).get("SAVER_COUNTER"))
            if data.get("telemetry", {}).get("SAVER_COUNTER") is not None
            else None
        ),
    ),
    EssencySensorEntityDescription(
        key="device_ip",
        name="Device IP Address",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("attributes", {}).get("csoDeviceIp"),
    ),
    EssencySensorEntityDescription(
        key="firmware_version",
        name="Firmware Version",
        icon="mdi:cellphone-arrow-down",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("attributes", {}).get("csoFwVersion"),
    ),
    EssencySensorEntityDescription(
        key="wifi_firmware_version",
        name="Wi-Fi Firmware Version",
        icon="mdi:wifi-cog",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("telemetry", {}).get("csoWfVersion"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Essency sensor entities."""
    coordinator: EssencyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        EssencySensor(coordinator, desc) for desc in SENSOR_DESCRIPTIONS
    ]
    # Add persistent Energy Meter sensor
    entities.append(EssencyEnergySensor(coordinator))

    async_add_entities(entities)


class EssencySensor(EssencyEntity, SensorEntity):
    """Standard Essency Sensor entity."""

    entity_description: EssencySensorEntityDescription

    def __init__(
        self,
        coordinator: EssencyDataUpdateCoordinator,
        description: EssencySensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, key=description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        if self._key == "heat_source":
            attrs = self.attributes
            return {
                "is_heating": self.coordinator.data.get("is_heating", False),
                "power_w": self.coordinator.data.get("power_w", 0.0),
                "hot_water_level": attrs.get("csoHotWaterLevel"),
                "hardware_heat_source_id": attrs.get("csoHeatSource", 0),
            }
        return None


class EssencyEnergySensor(EssencyEntity, RestoreSensor):
    """Cumulative Energy Usage Sensor for Home Assistant Energy Dashboard."""

    _attr_name = "Estimated Energy Usage"
    _attr_icon = "mdi:lightning-bolt-circle"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: EssencyDataUpdateCoordinator) -> None:
        """Initialize persistent energy sensor."""
        super().__init__(coordinator, key="energy_usage_kwh")

    async def async_added_to_hass(self) -> None:
        """Restore previous cumulative state when Home Assistant starts."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_sensor_data()
        if last_state and last_state.native_value is not None:
            try:
                prev_kwh = float(last_state.native_value)
                self.coordinator.set_restored_energy(prev_kwh)
            except (ValueError, TypeError):
                pass

    @property
    def native_value(self) -> float | None:
        """Return integrated cumulative energy in kWh."""
        return self.coordinator.data.get("energy_kwh", 0.0)
