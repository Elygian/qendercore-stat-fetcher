from __future__ import annotations

from typing import Final

DOMAIN: Final = "qendercore"

AUTH_URL: Final = "https://auth.qendercore.com:8000/v1/auth/login"
ACCOUNT_INFO_URL: Final = "https://api.qendercore.com:8000/v1/s/accountinfo"
DASHBOARD_URL: Final = "https://api.qendercore.com:8000/v1/h/views/dashboard"
DATASET_URL: Final = "https://api.qendercore.com:8000/v1/h/ds"

DEFAULT_CLIENT_SEQ: Final = "W.3.2"
DEFAULT_TIMEOUT: Final = 30
DEFAULT_SCAN_INTERVAL_SECONDS: Final = 60
MIN_SCAN_INTERVAL_SECONDS: Final = 30

CONF_HARDWARE_ID: Final = "hardware_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"

ATTR_TIMESTAMP: Final = "timestamp"
ATTR_TIMEZONE: Final = "timezone"

DATASET_PROPS: Final[list[str]] = [
    "inv.core.solar_prod_pwr_w",
    "inv.core.consumption_pwr_w",
    "inv.core.meter_pwr_w",
    "inv.core.battery_pwr_w",
    "inv.core.batt_soc_perc",
]
