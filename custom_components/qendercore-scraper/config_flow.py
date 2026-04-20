from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import QendercoreApiError, QendercoreAuthError, QendercoreClient
from .const import (
    CONF_HARDWARE_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MIN_SCAN_INTERVAL_SECONDS,
)


def _build_user_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")): str,
        }
    )


def _build_options_schema(options: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_SECONDS)),
            vol.Optional(
                CONF_HARDWARE_ID,
                default=options.get(CONF_HARDWARE_ID, ""),
            ): str,
        }
    )


class QendercoreConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qendercore."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].strip().lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = QendercoreClient(
                session=session,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                timeout=DEFAULT_TIMEOUT,
            )

            try:
                await client.async_validate_credentials()
                hardware_id = await client.async_discover_hardware_id()
            except QendercoreAuthError:
                errors["base"] = "invalid_auth"
            except QendercoreApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Qendercore {hardware_id[:8]}",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_HARDWARE_ID: hardware_id,
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(user_input),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> QendercoreOptionsFlow:
        return QendercoreOptionsFlow(config_entry)


class QendercoreOptionsFlow(OptionsFlow):
    """Handle Qendercore options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            manual_hardware_id = user_input.get(CONF_HARDWARE_ID, "").strip()
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_HARDWARE_ID: manual_hardware_id,
                },
            )

        current_options = {
            CONF_SCAN_INTERVAL: self.config_entry.options.get(
                CONF_SCAN_INTERVAL,
                self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
            ),
            CONF_HARDWARE_ID: self.config_entry.options.get(
                CONF_HARDWARE_ID,
                self.config_entry.data.get(CONF_HARDWARE_ID, ""),
            ),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(current_options),
        )