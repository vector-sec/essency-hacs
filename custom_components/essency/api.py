"""API client for Essency Water Heater ThingsBoard backend."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
import requests

from urllib3.util import Retry
from requests.adapters import HTTPAdapter

from .const import DEFAULT_HOST

_LOGGER = logging.getLogger(__name__)


class EssencyAuthError(Exception):
    """Exception raised when authentication fails."""


class EssencyConnectionError(Exception):
    """Exception raised when communication with server fails."""


class EssencyApiClient:
    """Async API Client for Essency Cloud ThingsBoard."""

    def __init__(
        self,
        username: str,
        password: str,
        host: str = DEFAULT_HOST,
        session: requests.Session | None = None,
    ) -> None:
        """Initialize API client."""
        self.username = username
        self.password = password
        self.host = host.rstrip("/")
        self._session = session or requests.Session()
        
        # Configure robust connection pooling with retries for transient socket drops
        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=5, pool_maxsize=5)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        self._token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0.0

    def _sync_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> requests.Response:
        """Perform a synchronous HTTP request with automatic token refresh."""
        url = f"{self.host}{endpoint}"
        req_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            req_headers.update(headers)

        if self._token and "X-Authorization" not in req_headers:
            req_headers["X-Authorization"] = f"Bearer {self._token}"

        for attempt in range(2):
            try:
                resp = self._session.request(
                    method,
                    url,
                    json=json_data,
                    headers=req_headers,
                    params=params,
                    timeout=15,
                )

                # Check if token expired and refresh
                if resp.status_code == 401 and retry_auth and endpoint != "/api/auth/login":
                    _LOGGER.debug("Token expired, attempting re-login")
                    self._sync_login()
                    req_headers["X-Authorization"] = f"Bearer {self._token}"
                    return self._session.request(
                        method,
                        url,
                        json=json_data,
                        headers=req_headers,
                        params=params,
                        timeout=15,
                    )

                return resp
            except (requests.ConnectionError, requests.Timeout) as err:
                if attempt == 0:
                    _LOGGER.debug("Socket dropped by remote server (%s), retrying request...", err)
                    time.sleep(0.5)
                    continue
                raise EssencyConnectionError(f"HTTP request to {url} failed: {err}") from err
            except requests.RequestException as err:
                raise EssencyConnectionError(f"HTTP request to {url} failed: {err}") from err

    def _sync_login(self) -> dict[str, Any]:
        """Perform synchronous login and store JWT tokens."""
        url = f"{self.host}/api/auth/login"
        payload = {"username": self.username, "password": self.password}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        try:
            resp = self._session.post(url, json=payload, headers=headers, timeout=15)
        except requests.RequestException as err:
            raise EssencyConnectionError(f"Login connection failed: {err}") from err

        if resp.status_code == 401:
            raise EssencyAuthError("Invalid Essency username or password")
        if resp.status_code != 200:
            raise EssencyConnectionError(f"Login failed with status {resp.status_code}: {resp.text}")

        data = resp.json()
        self._token = data.get("token")
        self._refresh_token = data.get("refreshToken")
        # Tokens are generally valid for 1 hour; refresh slightly early
        self._token_expiry = time.time() + 3000
        return data

    async def async_login(self) -> dict[str, Any]:
        """Asynchronously authenticate with Essency backend."""
        return await asyncio.to_thread(self._sync_login)

    async def async_get_current_user(self) -> dict[str, Any]:
        """Get current user information including customerId."""
        def _get():
            resp = self._sync_request("GET", "/api/auth/user")
            resp.raise_for_status()
            return resp.json()

        return await asyncio.to_thread(_get)

    async def async_get_devices(self, customer_id: str | None = None) -> list[dict[str, Any]]:
        """Fetch all devices assigned to this user/customer."""
        def _get():
            devices: list[dict[str, Any]] = []
            if customer_id:
                try:
                    resp = self._sync_request("GET", f"/api/customer/{customer_id}/devices?pageSize=50&page=0")
                    if resp.status_code == 200:
                        data = resp.json()
                        devices = data.get("data", [])
                except Exception as err:
                    _LOGGER.warning("Could not fetch customer devices: %s", err)

            if not devices:
                for fallback in ["/api/user/devices", f"/api/customer/device/{customer_id}"]:
                    try:
                        resp = self._sync_request("GET", fallback)
                        if resp.status_code == 200:
                            data = resp.json()
                            devices = data if isinstance(data, list) else data.get("data", [])
                            if devices:
                                break
                    except Exception:
                        continue

            return devices

        return await asyncio.to_thread(_get)

    async def async_get_attributes(self, device_id: str) -> dict[str, Any]:
        """Fetch all attributes (client, shared, server scope) for a device."""
        def _get():
            resp = self._sync_request("GET", f"/api/plugins/telemetry/DEVICE/{device_id}/values/attributes")
            resp.raise_for_status()
            data = resp.json()
            # Normalize list of {key, value, lastUpdateTs} into a dictionary
            result = {}
            if isinstance(data, list):
                for item in data:
                    result[item.get("key")] = item.get("value")
            elif isinstance(data, dict):
                result = data
            return result

        return await asyncio.to_thread(_get)

    async def async_get_telemetry(self, device_id: str) -> dict[str, Any]:
        """Fetch latest telemetry metrics for a device."""
        def _get():
            resp = self._sync_request("GET", f"/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries")
            resp.raise_for_status()
            data = resp.json()
            # Normalize latest telemetry into dictionary of key: value
            result = {}
            if isinstance(data, dict):
                for key, values in data.items():
                    if values and isinstance(values, list):
                        result[key] = values[0].get("value")
            return result

        return await asyncio.to_thread(_get)

    async def async_set_temperature(self, device_id: str, temperature_f: int | float) -> bool:
        """Set target water heater temperature in °F."""
        def _set():
            temp_int = int(round(temperature_f))
            # Send shared attribute update
            url = f"/api/plugins/telemetry/DEVICE/{device_id}/SHARED_SCOPE"
            payload = {"csoTempSetValue": temp_int, "shmTempSetValue": temp_int}
            resp = self._sync_request("POST", url, json_data=payload)
            
            # Also try two-way RPC
            try:
                rpc_url = f"/api/plugins/rpc/twoway/{device_id}"
                self._sync_request("POST", rpc_url, json_data={"method": "setTemperature", "params": temp_int})
            except Exception:
                pass

            return resp.status_code in (200, 204)

        return await asyncio.to_thread(_set)

    async def async_set_heat_mode(self, device_id: str, mode: int) -> bool:
        """Set the heat mode on the water heater."""
        def _set():
            # Send shared attribute update
            url = f"/api/plugins/telemetry/DEVICE/{device_id}/SHARED_SCOPE"
            payload = {"shmHeatMode": mode}
            resp = self._sync_request("POST", url, json_data=payload)

            # Also try two-way RPC
            try:
                rpc_url = f"/api/plugins/rpc/twoway/{device_id}"
                self._sync_request("POST", rpc_url, json_data={"method": "setHeatMode", "params": mode})
            except Exception:
                pass

            return resp.status_code in (200, 204)

        return await asyncio.to_thread(_set)

    async def async_set_boost(self, device_id: str, enable: bool) -> bool:
        """Activate or deactivate temporary boost mode."""
        def _set():
            now_ts = int(time.time())
            url = f"/api/plugins/telemetry/DEVICE/{device_id}/SHARED_SCOPE"
            if enable:
                # 1 hour boost default
                payload = {
                    "shmBoostStartTs": now_ts,
                    "shmBoostEndTs": now_ts + 3600,
                }
            else:
                payload = {
                    "shmBoostStartTs": now_ts,
                    "shmBoostEndTs": now_ts,
                }
            resp = self._sync_request("POST", url, json_data=payload)
            return resp.status_code in (200, 204)

        return await asyncio.to_thread(_set)

    async def async_set_vacation(self, device_id: str, enable: bool, days: int = 7) -> bool:
        """Activate or deactivate vacation mode."""
        def _set():
            now_ts = int(time.time())
            url = f"/api/plugins/telemetry/DEVICE/{device_id}/SHARED_SCOPE"
            if enable:
                payload = {
                    "shmVacationStartTs": now_ts,
                    "shmVacationEndTs": now_ts + (days * 86400),
                }
            else:
                payload = {
                    "shmVacationStartTs": now_ts,
                    "shmVacationEndTs": now_ts,
                }
            resp = self._sync_request("POST", url, json_data=payload)
            return resp.status_code in (200, 204)

        return await asyncio.to_thread(_set)

    async def async_set_water_saver(
        self, device_id: str, enable: bool, duration_minutes: int = 10
    ) -> bool:
        """Activate or deactivate water saver mode with a specified duration in minutes."""
        def _set():
            now_ts = int(time.time())
            url = f"/api/plugins/telemetry/DEVICE/{device_id}/SHARED_SCOPE"
            duration_secs = max(1, int(duration_minutes)) * 60
            payload = {
                "shmSaverStartTs": now_ts if enable else now_ts,
                "shmSaverEndTs": (now_ts + duration_secs) if enable else now_ts,
            }
            resp = self._sync_request("POST", url, json_data=payload)
            return resp.status_code in (200, 204)

        return await asyncio.to_thread(_set)
