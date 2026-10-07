"""DataUpdateCoordinator for Essency Water Heater integration."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EssencyApiClient, EssencyAuthError, EssencyConnectionError
from .const import DOMAIN, DEFAULT_POWER_RATING, DEFAULT_SAVER_DURATION

_LOGGER = logging.getLogger(__name__)


class EssencyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Essency data and energy integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EssencyApiClient,
        device_id: str,
        device_info_dict: dict[str, Any],
        update_interval: timedelta,
        power_rating_w: int = DEFAULT_POWER_RATING,
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
        self.power_rating_w = power_rating_w
        self.water_saver_duration = water_saver_duration

        # Energy tracking state
        self._last_update_ts = time.time()
        self.total_energy_kwh: float = 0.0
        self._energy_initialized = False

    def set_restored_energy(self, restored_kwh: float) -> None:
        """Restore previous cumulative energy usage from Home Assistant storage."""
        if not self._energy_initialized and restored_kwh > 0:
            self.total_energy_kwh = restored_kwh
            self._energy_initialized = True
            _LOGGER.debug("Restored cumulative energy to %.3f kWh", restored_kwh)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest device attributes, telemetry, and calculate energy."""
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

            # 3. Calculate virtual real-time power & integrate cumulative energy
            now = time.time()
            dt_hours = max(0.0, (now - self._last_update_ts) / 3600.0)
            self._last_update_ts = now

            # Determine heating state
            # - Heat mode 0 (OFF): heater is powered down
            # - Vacation mode: maintains minimal freeze protection (no normal heating)
            # - Boost mode: forces continuous maximum heating
            # - csoHotWaterLevel < 100: tank is depleted and dual 4.5 kW elements are actively recovering
            heat_mode = int(attributes.get("csmHeatMode", 3) or 3)
            vacation_status = int(attributes.get("csmVacationStatus", 0) or 0)
            boost_status = int(attributes.get("csmBoostStatus", 0) or 0)
            hot_water_level = attributes.get("csoHotWaterLevel")
            raw_heat_source = int(attributes.get("csoHeatSource", 0) or 0)

            is_heating = False
            if heat_mode == 0:  # HEAT_MODE_OFF
                is_heating = False
            elif vacation_status > 0 or heat_mode == 5:  # HEAT_MODE_VACATION
                is_heating = False
            elif boost_status > 0:
                is_heating = True
            elif raw_heat_source > 0:
                is_heating = True
            elif hot_water_level is not None:
                # Water heater elements are energized when tank is recovering capacity below 100%
                is_heating = int(hot_water_level) < 100

            # Real-time power draw
            current_power_w = self.power_rating_w if is_heating else 0.0

            # Riemann sum energy integration (kWh)
            if is_heating and dt_hours > 0 and dt_hours < 1.0:  # Ignore large gaps like restarts
                delta_kwh = (self.power_rating_w / 1000.0) * dt_hours
                self.total_energy_kwh += delta_kwh

            combined_data["power_w"] = current_power_w
            combined_data["energy_kwh"] = round(self.total_energy_kwh, 3)
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
