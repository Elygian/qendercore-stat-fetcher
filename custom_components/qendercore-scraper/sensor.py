from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import QendercoreRuntimeData
from .const import ATTR_TIMESTAMP, ATTR_TIMEZONE, DOMAIN
from .coordinator import QendercoreCoordinator


@dataclass(frozen=True, kw_only=True)
class QendercoreSensorDescription(SensorEntityDescription):
    value_key: str


SENSORS: tuple[QendercoreSensorDescription, ...] = (
    QendercoreSensorDescription(
        key="solar_production_power_w",
        value_key="solar_production_power_w",
        translation_key="solar_production_power",
        name="Solar Production Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QendercoreSensorDescription(
        key="consumption_power_w",
        value_key="consumption_power_w",
        translation_key="consumption_power",
        name="Consumption Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QendercoreSensorDescription(
        key="meter_power_w",
        value_key="meter_power_w",
        translation_key="meter_power",
        name="Meter Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QendercoreSensorDescription(
        key="grid_import_w",
        value_key="grid_import_w",
        translation_key="grid_import_power",
        name="Grid Import Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QendercoreSensorDescription(
        key="inverter_battery_power_w",
        value_key="inverter_battery_power_w",
        translation_key="battery_power",
        name="Battery Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QendercoreSensorDescription(
        key="battery_soc_percent",
        value_key="battery_soc_percent",
        translation_key="battery_soc",
        name="Battery State of Charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QendercoreSensorDescription(
        key="grid_export_w",
        value_key="grid_export_w",
        translation_key="grid_export_power",
        name="Grid Export Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime_data: QendercoreRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator
    async_add_entities(
        QendercoreSensor(coordinator, description) for description in SENSORS
    )


class QendercoreSensor(CoordinatorEntity[QendercoreCoordinator], SensorEntity):
    entity_description: QendercoreSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QendercoreCoordinator,
        description: QendercoreSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.hardware_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.hardware_id)},
            manufacturer="Qendercore",
            model="Energy System",
            name=f"Qendercore {self.coordinator.hardware_id[:8]}",
        )

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.metrics.get(self.entity_description.value_key)

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        metrics = self.coordinator.data.metrics
        return {
            ATTR_TIMESTAMP: metrics.get(ATTR_TIMESTAMP),
            ATTR_TIMEZONE: metrics.get(ATTR_TIMEZONE),
        }