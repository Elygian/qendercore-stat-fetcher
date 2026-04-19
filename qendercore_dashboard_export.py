from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


AUTH_URL = "https://auth.qendercore.com:8000/v1/auth/login"
DASHBOARD_URL = "https://api.qendercore.com:8000/v1/h/views/dashboard"
DATASET_URL = "https://api.qendercore.com:8000/v1/h/ds"
DEFAULT_DASHBOARD_OUTPUT = "qendercore_dashboard.json"
DEFAULT_SANKEY_OUTPUT = "qendercore_sankey_stats.json"
DEFAULT_SIMPLIFIED_OUTPUT = "qendercore_stats_simple.json"
DEFAULT_TIMEOUT = 30
DEFAULT_CLIENT_SEQ = "W.3.2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Qendercore dashboard data and export the raw JSON payload."
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the dotenv file containing QENDERCORE_USERNAME and QENDERCORE_PASSWORD.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_DASHBOARD_OUTPUT,
        help=f"Path to write the raw dashboard payload. Default: {DEFAULT_DASHBOARD_OUTPUT}",
    )
    parser.add_argument(
        "--sankey-output",
        default=DEFAULT_SANKEY_OUTPUT,
        help=(
            "Path to write the raw sankey stats payload. "
            f"Default: {DEFAULT_SANKEY_OUTPUT}"
        ),
    )
    parser.add_argument(
        "--simple-output",
        default=DEFAULT_SIMPLIFIED_OUTPUT,
        help=(
            "Path to write the simplified stats payload. "
            f"Default: {DEFAULT_SIMPLIFIED_OUTPUT}"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds. Default: {DEFAULT_TIMEOUT}",
    )
    return parser.parse_args()


def load_credentials(env_file: str) -> tuple[str, str]:
    load_dotenv(env_file)

    username = os.getenv("QENDERCORE_USERNAME")
    password = os.getenv("QENDERCORE_PASSWORD")

    if not username or not password:
        raise ValueError(
            "Missing credentials. Set QENDERCORE_USERNAME and "
            "QENDERCORE_PASSWORD in your dotenv file."
        )

    return username, password


def fetch_bearer_token(session: requests.Session, username: str, password: str, timeout: int) -> str:
    response = session.post(
        AUTH_URL,
        data={"username": username, "password": password},
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "x-qc-client-seq": DEFAULT_CLIENT_SEQ,
        },
        timeout=timeout,
    )
    response.raise_for_status()

    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise ValueError("Login response did not contain access_token.")

    return token


def fetch_dashboard_payload(session: requests.Session, token: str, timeout: int) -> object:
    response = session.get(
        DASHBOARD_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "x-qc-client-seq": DEFAULT_CLIENT_SEQ,
            "Authorization": f"Bearer {token}",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def extract_hwid(dashboard_payload: object) -> str:
    if not isinstance(dashboard_payload, dict):
        raise ValueError("Dashboard response was not a JSON object.")

    try:
        return dashboard_payload["ds"]["dshwdts"]["dr"]["fch"]["hwid"]
    except KeyError as exc:
        raise ValueError("Could not find hwid in dashboard payload.") from exc


def fetch_sankey_stats(
    session: requests.Session, token: str, hwid: str, timeout: int
) -> object:
    response = session.post(
        DATASET_URL,
        json={
            "_ft": "hwm",
            "hwid": hwid,
            "props": [
                "inv.core.solar_prod_pwr_w",
                "inv.core.consumption_pwr_w",
                "inv.core.meter_pwr_w",
                "inv.core.battery_pwr_w",
                "inv.core.batt_soc_perc",
            ],
            "duration": "PT15M",
            "resolution": "last",
            "tz": "local",
        },
        headers={
            "Content-Type": "application/json",
            "x-qc-client-seq": DEFAULT_CLIENT_SEQ,
            "Authorization": f"Bearer {token}",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def simplify_sankey_stats(sankey_payload: object) -> dict[str, object]:
    if not isinstance(sankey_payload, dict):
        raise ValueError("Sankey response was not a JSON object.")

    columns = sankey_payload.get("cols")
    rows = sankey_payload.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list) or not rows:
        raise ValueError("Sankey response did not contain any rows.")

    latest_row = rows[0]
    if not isinstance(latest_row, list):
        raise ValueError("Sankey response row was not a list.")

    row_by_id: dict[str, object] = {}
    for column, value in zip(columns, latest_row):
        if isinstance(column, dict):
            column_id = column.get("id")
            if isinstance(column_id, str):
                row_by_id[column_id] = value

    meter_power = row_by_id.get("inv.core.meter_pwr_w")
    if not isinstance(meter_power, (int, float)):
        raise ValueError("Sankey response did not contain a numeric meter power value.")

    return {
        "timestamp": row_by_id.get("ts"),
        "timezone": sankey_payload.get("meta", {}).get("tz"),
        "solar_production_power_w": row_by_id.get("inv.core.solar_prod_pwr_w"),
        "consumption_power_w": row_by_id.get("inv.core.consumption_pwr_w"),
        "meter_power_w": meter_power,
        "inverter_battery_power_w": row_by_id.get("inv.core.battery_pwr_w"),
        "battery_soc_percent": row_by_id.get("inv.core.batt_soc_perc"),
        "grid_export_w": abs(min(meter_power, 0)),
    }


def write_json(payload: object, output_path: str) -> Path:
    destination = Path(output_path)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return destination


def main() -> int:
    args = parse_args()
    username, password = load_credentials(args.env_file)

    with requests.Session() as session:
        token = fetch_bearer_token(session, username, password, args.timeout)
        dashboard_payload = fetch_dashboard_payload(session, token, args.timeout)
        hwid = extract_hwid(dashboard_payload)
        sankey_payload = fetch_sankey_stats(session, token, hwid, args.timeout)
        simple_payload = simplify_sankey_stats(sankey_payload)

    output_path = write_json(dashboard_payload, args.output)
    sankey_output_path = write_json(sankey_payload, args.sankey_output)
    simple_output_path = write_json(simple_payload, args.simple_output)
    print(f"Saved dashboard payload to {output_path}")
    print(f"Saved sankey stats payload to {sankey_output_path}")
    print(f"Saved simplified stats payload to {simple_output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())