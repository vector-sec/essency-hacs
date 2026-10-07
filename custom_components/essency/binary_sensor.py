"""Binary sensor platform for Essency Water Heater integration."""

from __future__ import annotations

from typing import Any
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EssencyDataUpdateCoordinator
from .entity import EssencyEntity


@dataclass(frozen=True, kw_only=True)
class EssencyBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Essency binary sensor entity."""

    is_on_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[EssencyBinarySensorEntityDescription, ...] = (
    EssencyBinarySensorEntityDescription(
        key="heating_active",
        name="Heating Active",
        device_class=BinarySensorDeviceClass.HEAT,
        icon="mdi:fire",
        is_on_fn=lambda data: data.get("is_heating", False),
    ),
    EssencyBinarySensorEntityDescription(
        key="online",
        name="Cloud Connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.get("attributes", {}).get("active", True),
    ),
    EssencyBinarySensorEntityDescription(
        key="fw_updating",
        name="Firmware Update in Progress",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (
            isinstance(data.get("attributes", {}).get("csoFwUpdating"), dict)
            and data.get("attributes", {}).get("csoFwUpdating", {}).get("status", 0) > 0
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Essency binary sensor entities."""
    coordinator: EssencyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        EssencyBinarySensor(coordinator, desc) for desc in BINARY_SENSOR_DESCRIPTIONS
    )


class EssencyBinarySensor(EssencyEntity, BinarySensorEntity):
    """Essency Binary Sensor Entity."""

    entity_description: EssencyBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: EssencyDataUpdateCoordinator,
        description: EssencyBinarySensorEntityDescription,
    ) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator, key=description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true if binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)
