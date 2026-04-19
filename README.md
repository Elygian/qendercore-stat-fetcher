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
- Battery power
- Battery state of charge
- Grid export power