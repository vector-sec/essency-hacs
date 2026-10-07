"""DataUpdateCoordinator for Essency Water Heater integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EssencyApiClient, EssencyAuthError, EssencyConnectionError
from .const import DOMAIN, DEFAULT_SAVER_DURATION

_LOGGER = logging.getLogger(__name__)


class EssencyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Essency data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EssencyApiClient,
        device_id: str,
        device_info_dict: dict[str, Any],
        update_interval: timedelta,
        water_saver_duration: int = DEFAULT_SAVER_DURATION,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=update_interval,
        )
        self.api = api
        self.device_id = device_id
        self.device_info_dict = device_info_dict
        self.water_saver_duration = water_saver_duration

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest device attributes and telemetry."""
        try:
            # 1. Fetch attributes
            attributes = await self.api.async_get_attributes(self.device_id)

            # 2. Fetch latest telemetry
            telemetry = await self.api.async_get_telemetry(self.device_id)

            # Combine into unified state dictionary
            combined_data = {
                "attributes": attributes,
                "telemetry": telemetry,
                "device_id": self.device_id,
                "device_info": self.device_info_dict,
            }

            # Boost mode actively energizes heating elements
            boost_status = int(attributes.get("csmBoostStatus", 0) or 0)
            is_heating = boost_status > 0
            raw_heat_source = int(attributes.get("csoHeatSource", 0) or 0)

            combined_data["is_heating"] = is_heating
            combined_data["raw_heat_source"] = raw_heat_source

            return combined_data

        except EssencyAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except EssencyConnectionError as err:
            if self.data is not None:
                _LOGGER.warning(
                    "Temporary connection glitch talking to Essency server (%s); retaining last known values",
                    err,
                )
                return self.data
            raise UpdateFailed(f"Connection error fetching Essency data: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error updating Essency data: {err}") from err
