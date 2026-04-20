from __future__ import annotations

import logging
from datetime import timedelta
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import QendercoreApiError, QendercoreAuthError, QendercoreClient
from .const import CONF_HARDWARE_ID, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class QendercoreData:
    hardware_id: str
    metrics: dict[str, Any]


class QendercoreCoordinator(DataUpdateCoordinator[QendercoreData]):
    """Coordinator for Qendercore metrics."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: QendercoreClient,
        config_entry: ConfigEntry,
    ) -> None:
        update_interval_seconds = config_entry.options.get(
            CONF_SCAN_INTERVAL,
            config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.client = client
        self.config_entry = config_entry
        self.hardware_id = config_entry.options.get(CONF_HARDWARE_ID) or config_entry.data.get(CONF_HARDWARE_ID)

    async def _async_update_data(self) -> QendercoreData:
        try:
            hardware_id, metrics = await self.client.async_get_metrics(self.hardware_id)
        except QendercoreAuthError as err:
            raise ConfigEntryAuthFailed from err
        except QendercoreApiError as err:
            raise UpdateFailed(str(err)) from err

        if hardware_id != self.hardware_id:
            self.hardware_id = hardware_id
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_HARDWARE_ID: hardware_id},
            )

        return QendercoreData(hardware_id=hardware_id, metrics=metrics)