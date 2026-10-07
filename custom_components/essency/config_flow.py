"""Config flow for Essency Water Heater integration."""

from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import EssencyApiClient, EssencyAuthError, EssencyConnectionError
from .const import (
    DOMAIN,
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

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=300)
        ),
        vol.Optional(CONF_POWER_RATING, default=DEFAULT_POWER_RATING): vol.All(
            vol.Coerce(int), vol.Range(min=1000, max=10000)
        ),
    }
)


class EssencyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Essency Water Heater."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD].strip()
            host = user_input.get(CONF_HOST, DEFAULT_HOST).strip()

            api = EssencyApiClient(username=username, password=password, host=host)

            try:
                # Validate login
                await api.async_login()

                # Get user & devices to determine unique ID
                user_info = await api.async_get_current_user()
                customer_id = user_info.get("customerId", {}).get("id")
                devices = await api.async_get_devices(customer_id)

                if not devices:
                    errors["base"] = "no_devices_found"
                else:
                    device = devices[0]
                    device_id = device.get("id", {}).get("id")
                    device_name = device.get("name", "Essency Water Heater")

                    await self.async_set_unique_id(device_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Essency ({device_name})",
                        data=user_input,
                    )

            except EssencyAuthError:
                errors["base"] = "invalid_auth"
            except EssencyConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception in config flow: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return EssencyOptionsFlowHandler(config_entry)


class EssencyOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Essency integration options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL,
                        self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                vol.Optional(
                    CONF_POWER_RATING,
                    default=self.config_entry.options.get(
                        CONF_POWER_RATING,
                        self.config_entry.data.get(CONF_POWER_RATING, DEFAULT_POWER_RATING),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1000, max=10000)),
                vol.Optional(
                    CONF_SAVER_DURATION,
                    default=self.config_entry.options.get(
                        CONF_SAVER_DURATION,
                        self.config_entry.data.get(CONF_SAVER_DURATION, DEFAULT_SAVER_DURATION),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
