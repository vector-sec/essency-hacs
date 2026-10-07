"""Switch platform for Essency Water Heater integration."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EssencyDataUpdateCoordinator
from .entity import EssencyEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Essency switches."""
    coordinator: EssencyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            EssencyBoostSwitch(coordinator),
            EssencySaverSwitch(coordinator),
            EssencyVacationSwitch(coordinator),
        ]
    )


class EssencyBaseSwitch(EssencyEntity, SwitchEntity):
    """Base class for Essency switches with optimistic state tracking."""

    def __init__(
        self,
        coordinator: EssencyDataUpdateCoordinator,
        key: str,
        status_key: str,
    ) -> None:
        """Initialize base switch."""
        super().__init__(coordinator, key=key)
        self._status_key = status_key
        self._optimistic_state: bool | None = None
        self._optimistic_until: float = 0.0

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        hw_on = int(self.attributes.get(self._status_key, 0) or 0) > 0

        if self._optimistic_state is not None:
            if time.time() < self._optimistic_until:
                if hw_on == self._optimistic_state:
                    # Hardware has confirmed desired state
                    self._optimistic_state = None
                    return hw_on
                # Hold optimistic state while hardware processes command
                return self._optimistic_state
            # Window expired without hardware confirmation
            self._optimistic_state = None

        return hw_on

    async def _async_handle_toggle(self, target_state: bool, api_coro: Any) -> None:
        """Handle toggling the switch with optimistic state and confirmation polling."""
        self._optimistic_state = target_state
        self._optimistic_until = time.time() + 25.0
        self.async_write_ha_state()

        try:
            await api_coro
        except Exception:
            self._optimistic_state = None
            self._optimistic_until = 0.0
            self.async_write_ha_state()
            raise

        # Poll coordinator in background to catch device confirmation promptly
        self.hass.async_create_task(self._async_poll_confirmation())

    async def _async_poll_confirmation(self) -> None:
        """Poll coordinator at intervals to confirm hardware state update."""
        for delay in (2.0, 3.0, 5.0):
            await asyncio.sleep(delay)
            if self._optimistic_state is None:
                # Already confirmed or cancelled
                break
            await self.coordinator.async_request_refresh()


class EssencyBoostSwitch(EssencyBaseSwitch):
    """Switch to activate or cancel Boost mode."""

    _attr_name = "Boost Mode"
    _attr_icon = "mdi:rocket-launch"

    def __init__(self, coordinator: EssencyDataUpdateCoordinator) -> None:
        """Initialize boost switch."""
        super().__init__(coordinator, key="boost_switch", status_key="csmBoostStatus")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate boost mode."""
        await self._async_handle_toggle(
            True,
            self.coordinator.api.async_set_boost(self.coordinator.device_id, True),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Cancel boost mode."""
        await self._async_handle_toggle(
            False,
            self.coordinator.api.async_set_boost(self.coordinator.device_id, False),
        )


class EssencySaverSwitch(EssencyBaseSwitch):
    """Switch to activate or cancel Water Saver mode."""

    _attr_name = "Water Saver Mode"
    _attr_icon = "mdi:leaf"

    def __init__(self, coordinator: EssencyDataUpdateCoordinator) -> None:
        """Initialize water saver switch."""
        super().__init__(coordinator, key="water_saver_switch", status_key="csmSaverStatus")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate water saver mode with configured duration."""
        duration = getattr(self.coordinator, "water_saver_duration", 10)
        await self._async_handle_toggle(
            True,
            self.coordinator.api.async_set_water_saver(
                self.coordinator.device_id, True, duration_minutes=duration
            ),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Cancel water saver mode."""
        await self._async_handle_toggle(
            False,
            self.coordinator.api.async_set_water_saver(self.coordinator.device_id, False),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes including configured duration and remaining time."""
        attrs = self.attributes
        now_ts = int(time.time())
        end_ts = int(attrs.get("csmSaverEndTs") or 0)
        remaining_secs = max(0, end_ts - now_ts) if self.is_on else 0
        return {
            "configured_duration_minutes": getattr(self.coordinator, "water_saver_duration", 10),
            "remaining_seconds": remaining_secs,
            "remaining_minutes": round(remaining_secs / 60.0, 1),
        }


class EssencyVacationSwitch(EssencyBaseSwitch):
    """Switch to activate or cancel Vacation mode."""

    _attr_name = "Vacation Mode"
    _attr_icon = "mdi:bag-suitcase"

    def __init__(self, coordinator: EssencyDataUpdateCoordinator) -> None:
        """Initialize vacation switch."""
        super().__init__(coordinator, key="vacation_switch", status_key="csmVacationStatus")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate vacation mode."""
        await self._async_handle_toggle(
            True,
            self.coordinator.api.async_set_vacation(self.coordinator.device_id, True),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Cancel vacation mode."""
        await self._async_handle_toggle(
            False,
            self.coordinator.api.async_set_vacation(self.coordinator.device_id, False),
        )
