# Qendercore Home Assistant Integration

Custom Home Assistant integration for Qendercore energy systems.

This repository is structured primarily as a HACS custom integration. The Home Assistant payload lives under `custom_components/qendercore`. Useful API reference material (created and meant to be used with [Bruno](https://www.usebruno.com/)) now live under `helpers/api_collection`. A standalone script using the same API calls and payload transformation logic is available at `helpers/qendercore_dashboard_export.py`

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Elygian&repository=qendercore-stat-fetcher&category=integration)

## Repository layout

- `custom_components/qendercore/`: the Home Assistant integration
- `helpers/qendercore_dashboard_export.py`: standalone exporter for direct API inspection
- `helpers/api_collection/`: Bruno request files used for API exploration. Contains some scripting to simplify usage, and relies on an environment (detailed below)

## Current status

Initial implementation is in progress. The integration currently includes:

- Config flow using Qendercore username and password
- Hardware ID auto-discovery with manual override support
- Coordinator-based polling
- Sensor entities for the metrics currently exposed by the existing script

## Current sensors

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

## Helper utilities

The helper assets are optional and are not used by the Home Assistant integration at runtime.

- `helpers/qendercore_dashboard_export.py` was originally written as an exploration of how the Qendercore API works and what metrics were available from it. Simply create a `.env` file with `QENDERCORE_USERNAME` and `QENDERCORE_PASSWORD` containing the same creds you use to log in to the dashboard.
- `helpers/api_collection/` contains the Bruno request set I used to inspect the Qendercore API before I started working on the HA integration.

You need to set up an environment within Bruno with the same credentials as the `.env` mentioned above. The hwid and token will be set automagically by the post response scripts.