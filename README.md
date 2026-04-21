# Qendercore Home Assistant Integration

Custom Home Assistant integration for Qendercore energy systems.

This repository is structured primarily as a HACS custom integration. The Home Assistant payload lives under `custom_components/qendercore`. Useful API reference material (created and meant to be used with [Bruno](https://www.usebruno.com/)) now live under `helpers/api_collection`. A standalone script using the same API calls and payload transformation logic is available at `helpers/qendercore_dashboard_export.py`

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Elygian&repository=qendercore-stat-fetcher&category=integration)

## Disclaimer

This project is an independent, community-maintained Home Assistant integration and is not affiliated with, endorsed by, or sponsored by Soltaro, Qendercore, or their related companies.

Any company names, product names, app names, and logos used in this repository remain the property of their respective owners and are included only to identify compatibility with the upstream platform.

## Repository layout

- `custom_components/qendercore/`: the Home Assistant integration
- `helpers/qendercore_dashboard_export.py`: standalone exporter for direct API inspection
- `helpers/api_collection/`: Bruno request files used for API exploration. Contains some scripting to simplify usage, and relies on an environment (detailed below)

## Current status

The integration currently includes:

- Config flow using Qendercore username and password
- Hardware ID auto-discovery with manual override support
- Coordinator-based polling
- Token reuse with re-authentication on 401 responses
- Sensor entities for the metrics currently exposed by the existing script

## Setup and runtime behavior

- Initial setup asks for username and password and validates them against the live Qendercore login endpoint.
- During setup, the integration attempts to discover the hardware ID automatically and stores the resolved value in the config entry.
- The integration exposes an options flow for polling interval and manual hardware ID override.
- The default polling interval is 60 seconds.
- The minimum supported polling interval is 30 seconds.

## Hardware ID discovery

The integration discovers the hardware ID automatically rather than hard-coding a single field path.

Current discovery order:

- Log in and obtain a bearer token
- Query `GET /v1/s/accountinfo`
- Search the returned JSON recursively for UUID-like values near keys containing terms such as `hwid`, `hardware`, `device`, or `gateway`
- If that fails, query `GET /v1/h/views/dashboard`
- Run the same recursive search on the dashboard payload

If discovery succeeds, the resolved hardware ID is used for later dataset polling. A manual override can be set from the integration options if needed.

## Data fetching logic

The integration uses a single Home Assistant `DataUpdateCoordinator` for polling. That means one shared API refresh populates all sensor entities, rather than each sensor performing its own request.

The main live dataset call currently requests these Qendercore properties:

- `inv.core.solar_prod_pwr_w`
- `inv.core.consumption_pwr_w`
- `inv.core.meter_pwr_w`
- `inv.core.battery_pwr_w`
- `inv.core.batt_soc_perc`

The raw API payload is then normalized into a simpler metrics dictionary before entity updates.

## Current sensors

- Solar production power
- Consumption power
- Meter power
- Grid import power
- Battery power
- Battery state of charge
- Grid export power

## Sensor logic

- `Meter power` is the signed meter value returned by the API.
- `Grid import power` is derived as the positive portion of meter power.
- `Grid export power` is derived as the absolute value of the negative portion of meter power.
- `Battery power` is currently exposed as the raw signed battery power value returned by the API.
- `Battery state of charge` is exposed as a percentage sensor.

All current entities are sensors under one Qendercore device and include timestamp and timezone as extra state attributes.

## Energy Dashboard notes

The power sensors exposed by this integration use `device_class: power`, `state_class: measurement`, and watt units, which is correct for instantaneous electricity sensors.

Home Assistant's Energy Dashboard typically needs cumulative energy sensors for long-term usage and return, using `device_class: energy` and `state_class: total` or `total_increasing`, usually in `kWh` or `Wh`.

That means the current Qendercore entities are suitable as source power sensors, but not yet as direct Energy Dashboard energy entities. For testing today, create Home Assistant Integration helper sensors from these power entities:

- Solar production from `sensor.qendercore_solar_production_power`
- Grid import from `sensor.qendercore_grid_import_power`
- Grid export from `sensor.qendercore_grid_export_power`

Those helper-created energy sensors can then be selected in the Energy Dashboard if they show valid long-term statistics.

## Current limitations

- The integration currently exposes live power and SOC sensors, not native cumulative energy sensors.
- Home Assistant Energy Dashboard usage still relies on Integration helpers for energy accumulation.
- Only one resolved hardware ID is handled per config entry.
- There is currently no UI for selecting between multiple devices if the account exposes more than one candidate hardware ID.
- The battery power sign convention is passed through from the Qendercore API as-is; the integration does not yet split this into separate charge and discharge sensors.
- Request timeout is fixed in code at 30 seconds.
- The integration currently exposes only the sensor platform.

## Helper utilities

The helper assets are optional and are not used by the Home Assistant integration at runtime.

- `helpers/qendercore_dashboard_export.py` was originally written as an exploration of how the Qendercore API works and what metrics were available from it. Simply create a `.env` file with `QENDERCORE_USERNAME` and `QENDERCORE_PASSWORD` containing the same creds you use to log in to the dashboard.
- `helpers/api_collection/` contains the Bruno request set I used to inspect the Qendercore API before I started working on the HA integration.

You need to set up an environment within Bruno with the same credentials as the `.env` mentioned above. The hwid and token will be set automagically by the post response scripts.