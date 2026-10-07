"""The Essency Water Heater integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import EssencyApiClient, EssencyAuthError, EssencyConnectionError
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    CONF_POWER_RATING,
    CONF_SAVER_DURATION,
    DEFAULT_HOST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_POWER_RATING,
    DEFAULT_SAVER_DURATION,
)
from .coordinator import EssencyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Essency Water Heater from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    host = entry.data.get(CONF_HOST, DEFAULT_HOST)

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    power_rating = entry.options.get(
        CONF_POWER_RATING,
        entry.data.get(CONF_POWER_RATING, DEFAULT_POWER_RATING),
    )
    saver_duration = entry.options.get(
        CONF_SAVER_DURATION,
        entry.data.get(CONF_SAVER_DURATION, DEFAULT_SAVER_DURATION),
    )

    api = EssencyApiClient(username=username, password=password, host=host)

    try:
        await api.async_login()
        user_info = await api.async_get_current_user()
        customer_id = user_info.get("customerId", {}).get("id")
        devices = await api.async_get_devices(customer_id)

        if not devices:
            _LOGGER.error("No Essency water heater devices found on this account")
            return False

        device = devices[0]
        device_id = device.get("id", {}).get("id")

    except EssencyAuthError as err:
        _LOGGER.error("Authentication failed during setup: %s", err)
        return False
    except EssencyConnectionError as err:
        raise ConfigEntryNotReady(f"Could not connect to Essency server: {err}") from err
    except Exception as err:
        raise ConfigEntryNotReady(f"Unexpected setup error: {err}") from err

    coordinator = EssencyDataUpdateCoordinator(
        hass=hass,
        api=api,
        device_id=device_id,
        device_info_dict=device,
        update_interval=timedelta(seconds=scan_interval),
        power_rating_w=power_rating,
        water_saver_duration=saver_duration,
    )

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Forward platform setups
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
