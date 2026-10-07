"""Base entity class for Essency Water Heater integration."""

from __future__ import annotations

from typing import Any
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EssencyDataUpdateCoordinator


class EssencyEntity(CoordinatorEntity[EssencyDataUpdateCoordinator]):
    """Base class for all Essency entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EssencyDataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize base Essency entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.device_id}_{key}"

    @property
    def attributes(self) -> dict[str, Any]:
        """Convenience property for device attributes."""
        return self.coordinator.data.get("attributes", {})

    @property
    def telemetry(self) -> dict[str, Any]:
        """Convenience property for device telemetry."""
        return self.coordinator.data.get("telemetry", {})

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant device registry info."""
        attrs = self.attributes
        device_sn = attrs.get("csoDeviceSn") or self.coordinator.device_info_dict.get("name")
        device_ip = attrs.get("csoDeviceIp")
        fw_ver = attrs.get("csoFwVersion") or self.telemetry.get("csoFwVersion")
        cb_ver = self.telemetry.get("csoCbVersion")
        name = attrs.get("ssaName") or "Essency Water Heater"

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            name=name,
            manufacturer="Essency",
            model="EXR / E55R",
            serial_number=device_sn,
            sw_version=fw_ver,
            hw_version=cb_ver,
            configuration_url=f"http://{device_ip}" if device_ip else None,
        )
