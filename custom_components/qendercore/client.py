from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    ACCOUNT_INFO_URL,
    AUTH_URL,
    DASHBOARD_URL,
    DATASET_PROPS,
    DATASET_URL,
    DEFAULT_CLIENT_SEQ,
)

_LOGGER = logging.getLogger(__name__)

_UUID_PATTERN = re.compile(
    r"(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_DISCOVERY_KEYWORDS = ("hwid", "hardware", "device", "gateway")


class QendercoreError(Exception):
    """Base exception for Qendercore integration errors."""


class QendercoreAuthError(QendercoreError):
    """Raised when authentication fails."""


class QendercoreApiError(QendercoreError):
    """Raised when the API returns an unexpected response."""


class QendercoreClient:
    """Qendercore API client."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        timeout: int,
        client_seq: str = DEFAULT_CLIENT_SEQ,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._timeout = timeout
        self._client_seq = client_seq
        self._token: str | None = None

    async def async_validate_credentials(self) -> None:
        """Validate that credentials can obtain a bearer token."""
        await self._async_login(force=True)

    async def async_get_metrics(self, hardware_id: str | None = None) -> tuple[str, dict[str, Any]]:
        """Return resolved hardware id and latest normalized metrics."""
        token = await self._async_login()
        resolved_hardware_id = hardware_id or await self.async_discover_hardware_id(token)
        payload = await self._async_request(
            "post",
            DATASET_URL,
            token=token,
            json={
                "_ft": "hwm",
                "hwid": resolved_hardware_id,
                "props": DATASET_PROPS,
                "duration": "PT15M",
                "resolution": "last",
                "tz": "local",
            },
        )
        return resolved_hardware_id, self._simplify_sankey_stats(payload)

    async def async_discover_hardware_id(self, token: str | None = None) -> str:
        """Discover the user's hardware id, preferring account info."""
        auth_token = token or await self._async_login()

        account_info = await self._async_request("get", ACCOUNT_INFO_URL, token=auth_token)
        discovered = self._extract_hardware_id(account_info)
        if discovered:
            return discovered

        dashboard_payload = await self._async_request("get", DASHBOARD_URL, token=auth_token)
        discovered = self._extract_hardware_id(dashboard_payload)
        if discovered:
            return discovered

        raise QendercoreApiError("Could not discover hardware id from Qendercore API responses.")

    async def _async_login(self, force: bool = False) -> str:
        if self._token and not force:
            return self._token

        try:
            response = await self._session.post(
                AUTH_URL,
                data={"username": self._username, "password": self._password},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "x-qc-client-seq": self._client_seq,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = await response.json()
        except ClientResponseError as err:
            raise QendercoreAuthError("Authentication with Qendercore failed.") from err
        except ClientError as err:
            raise QendercoreApiError("Could not reach Qendercore authentication service.") from err

        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise QendercoreAuthError("Authentication response did not contain an access token.")

        self._token = token
        return token

    async def _async_request(
        self,
        method: str,
        url: str,
        token: str | None = None,
        **kwargs: Any,
    ) -> Any:
        extra_headers = kwargs.pop("headers", {})
        request_headers = {
            "x-qc-client-seq": self._client_seq,
            **extra_headers,
        }
        if token:
            request_headers["Authorization"] = f"Bearer {token}"

        try:
            response = await getattr(self._session, method)(
                url,
                headers=request_headers,
                timeout=self._timeout,
                **kwargs,
            )
            response.raise_for_status()
            return await response.json()
        except ClientResponseError as err:
            if err.status == 401 and token is not None:
                _LOGGER.debug("Received 401 from Qendercore API, refreshing token")
                self._token = None
                refreshed_token = await self._async_login(force=True)
                return await self._async_request(
                    method,
                    url,
                    token=refreshed_token,
                    headers=extra_headers,
                    **kwargs,
                )
            if err.status in (401, 403):
                raise QendercoreAuthError("Qendercore rejected the request.") from err
            raise QendercoreApiError(f"Qendercore API request failed with status {err.status}.") from err
        except ClientError as err:
            raise QendercoreApiError("Could not reach Qendercore API.") from err

    def _extract_hardware_id(self, payload: Any, keyword_match: bool = False) -> str | None:
        if isinstance(payload, Mapping):
            for key, value in payload.items():
                next_keyword_match = keyword_match
                if isinstance(key, str) and any(keyword in key.lower() for keyword in _DISCOVERY_KEYWORDS):
                    next_keyword_match = True
                    candidate = self._coerce_hardware_id(value)
                    if candidate:
                        return candidate
                candidate = self._extract_hardware_id(value, next_keyword_match)
                if candidate:
                    return candidate

        if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
            for item in payload:
                candidate = self._extract_hardware_id(item, keyword_match)
                if candidate:
                    return candidate

        if keyword_match:
            return self._coerce_hardware_id(payload)

        return None

    def _coerce_hardware_id(self, value: Any) -> str | None:
        if isinstance(value, str) and _UUID_PATTERN.match(value):
            return value
        return None

    def _simplify_sankey_stats(self, sankey_payload: Any) -> dict[str, Any]:
        if not isinstance(sankey_payload, Mapping):
            raise QendercoreApiError("Sankey response was not a JSON object.")

        columns = sankey_payload.get("cols")
        rows = sankey_payload.get("rows")
        if not isinstance(columns, list) or not isinstance(rows, list) or not rows:
            raise QendercoreApiError("Sankey response did not contain any rows.")

        latest_row = rows[0]
        if not isinstance(latest_row, list):
            raise QendercoreApiError("Sankey response row was not a list.")

        row_by_id: dict[str, Any] = {}
        for column, value in zip(columns, latest_row, strict=False):
            if isinstance(column, Mapping):
                column_id = column.get("id")
                if isinstance(column_id, str):
                    row_by_id[column_id] = value

        meter_power = row_by_id.get("inv.core.meter_pwr_w")
        if not isinstance(meter_power, (int, float)):
            raise QendercoreApiError("Sankey response did not contain a numeric meter power value.")

        meta = sankey_payload.get("meta")
        timezone = meta.get("tz") if isinstance(meta, Mapping) else None

        return {
            "timestamp": row_by_id.get("ts"),
            "timezone": timezone,
            "solar_production_power_w": row_by_id.get("inv.core.solar_prod_pwr_w"),
            "consumption_power_w": row_by_id.get("inv.core.consumption_pwr_w"),
            "meter_power_w": meter_power,
            "grid_import_w": max(meter_power, 0),
            "inverter_battery_power_w": row_by_id.get("inv.core.battery_pwr_w"),
            "battery_soc_percent": row_by_id.get("inv.core.batt_soc_perc"),
            "grid_export_w": abs(min(meter_power, 0)),
        }