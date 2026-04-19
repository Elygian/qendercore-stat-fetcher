# Qendercore Home Assistant Integration

Custom Home Assistant integration for Qendercore energy systems.

## Current status

Initial implementation is in progress. The repository now includes a custom component scaffold under `custom_components/qendercore` with:

- Config flow using Qendercore username and password
- Hardware ID auto-discovery with manual override support
- Coordinator-based polling
- Sensor entities for the metrics currently exposed by the existing script

## Planned sensors

- Solar production power
- Consumption power
- Meter power
- Grid import power
- Battery power
- Battery state of charge
- Grid export power

## Energy Dashboard notes

The power sensors exposed by this integration use `device_class: power`, `state_class: measurement`, and watt units, which is correct for instantaneous electricity sensors.

Home Assistant's Energy Dashboard typically needs cumulative energy sensors for long-term usage and return, using `device_class: energy` and `state_class: total` or `total_increasing`, usually in `kWh` or `Wh`.

That means the current Qendercore entities are suitable as source power sensors, but not yet as direct Energy Dashboard energy entities. For testing today, create Home Assistant Integration helper sensors from these power entities:

- Solar production from `sensor.qendercore_solar_production_power`
- Grid import from `sensor.qendercore_grid_import_power`
- Grid export from `sensor.qendercore_grid_export_power`

Those helper-created energy sensors can then be selected in the Energy Dashboard if they show valid long-term statistics.