#!/usr/bin/env python3
"""Fetch Qendercore API stats using curl and export responses to a JSON file."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
	from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
	load_dotenv = None


DEFAULT_CLIENT_SEQ = "W.3.2"
HWID_PATTERN = re.compile(
	"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
HWID_CANDIDATE_KEYWORDS = (
	"hwid",
	"hardware_id",
	"hardwareid",
	"device_id",
	"deviceid",
	"gateway_id",
	"gatewayid",
)
SANKEY_LABELS = {
	"Solar Production Power (W)",
	"Consumption Power (W)",
	"Meter Power (W)",
	"Inverter Battery Power (W)",
	"Battery SOC (%)",
}
PIE_CHART_LABELS = {
	"Import Energy (kWh)",
	"Export Energy (kWh)",
	"Self-Consumption Energy (kWh)",
}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Fetch Qendercore stats by running curl requests from Python.",
	)
	parser.add_argument("--username", help="Login username (or set USERNAME env var).")
	parser.add_argument("--password", help="Login password (or set PASSWORD env var).")
	parser.add_argument(
		"--hwid",
		help="Optional hardware ID override for data requests (auto-discovered if omitted).",
	)
	parser.add_argument(
		"--start-date",
		default=date.today().isoformat(),
		help="Start date for day-based queries in YYYY-MM-DD format (default: today).",
	)
	parser.add_argument(
		"--client-seq",
		default=DEFAULT_CLIENT_SEQ,
		help=f"x-qc-client-seq header value (default: {DEFAULT_CLIENT_SEQ}).",
	)
	parser.add_argument(
		"--output",
		default="qendercore_stats_export.json",
		help="Output JSON file path (default: qendercore_stats_export.json).",
	)
	parser.add_argument(
		"--timeout",
		type=int,
		default=30,
		help="Curl timeout in seconds for each request (default: 30).",
	)
	parser.add_argument(
		"--pretty",
		action="store_true",
		help="Pretty-print exported JSON.",
	)
	return parser.parse_args()


def base_headers(client_seq: str) -> dict[str, str]:
	return {
		"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:149.0) Gecko/20100101 Firefox/149.0",
		"Accept": "application/json",
		"Accept-Language": "en-GB,en;q=0.9",
		"Accept-Encoding": "gzip, deflate, br, zstd",
		"Referer": "https://www.qendercore.com/",
		"x-qc-client-seq": client_seq,
		"Origin": "https://www.qendercore.com",
		"Sec-GPC": "1",
		"Connection": "keep-alive",
		"Sec-Fetch-Dest": "empty",
		"Sec-Fetch-Mode": "cors",
		"Sec-Fetch-Site": "same-site",
		"Priority": "u=0",
	}


def run_curl_json(
	*,
	url: str,
	method: str,
	headers: dict[str, str],
	timeout: int,
	form_fields: dict[str, str] | None = None,
	json_body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
	if shutil.which("curl") is None:
		raise RuntimeError("curl binary was not found in PATH.")

	cmd: list[str] = [
		"curl",
		"--silent",
		"--show-error",
		"--location",
		"--request",
		method,
		"--max-time",
		str(timeout),
		"--write-out",
		"\n%{http_code}",
		url,
	]

	for name, value in headers.items():
		cmd.extend(["--header", f"{name}: {value}"])

	if form_fields:
		for name, value in form_fields.items():
			cmd.extend(["--data-urlencode", f"{name}={value}"])

	if json_body is not None:
		cmd.extend(["--data-raw", json.dumps(json_body, separators=(",", ":"))])

	proc = subprocess.run(cmd, capture_output=True, text=True)
	if proc.returncode != 0:
		stderr = proc.stderr.strip() or "(no stderr)"
		raise RuntimeError(f"curl failed for {url}: {stderr}")

	if "\n" not in proc.stdout:
		raise RuntimeError(f"Unexpected curl output for {url}: {proc.stdout!r}")

	body_text, status_text = proc.stdout.rsplit("\n", 1)
	try:
		status_code = int(status_text.strip())
	except ValueError as exc:
		raise RuntimeError(f"Failed to parse HTTP status code: {status_text!r}") from exc

	body_text = body_text.strip()
	if not body_text:
		return status_code, None

	try:
		return status_code, json.loads(body_text)
	except json.JSONDecodeError:
		return status_code, body_text


def require_credentials(args: argparse.Namespace) -> tuple[str, str]:
	username = args.username or os.getenv("USERNAME")
	password = args.password or os.getenv("PASSWORD")
	if not username or not password:
		raise RuntimeError(
			"Missing credentials. Provide --username/--password or set USERNAME and PASSWORD in environment/.env.",
		)
	return username, password


def bearer_token(args: argparse.Namespace, headers: dict[str, str], username: str, password: str) -> str:
	auth_headers = dict(headers)
	auth_headers["Content-Type"] = "application/x-www-form-urlencoded"

	status, response = run_curl_json(
		url="https://auth.qendercore.com:8000/v1/auth/login",
		method="POST",
		headers=auth_headers,
		timeout=args.timeout,
		form_fields={"username": username, "password": password},
	)
	if status != 200 or not isinstance(response, dict):
		raise RuntimeError(f"Token request failed: HTTP {status}, response={response!r}")

	token = response.get("access_token")
	if not isinstance(token, str) or not token:
		raise RuntimeError(f"Token missing in auth response: {response!r}")
	return token


def iter_identifier_candidates(payload: Any) -> list[str]:
	candidates: list[str] = []

	def _walk(node: Any) -> None:
		if isinstance(node, dict):
			for key, value in node.items():
				lower_key = key.lower() if isinstance(key, str) else ""
				if any(keyword in lower_key for keyword in HWID_CANDIDATE_KEYWORDS) and isinstance(value, str):
					candidates.append(value.strip())
				_walk(value)
		elif isinstance(node, list):
			for item in node:
				_walk(item)

	_walk(payload)
	return candidates


def extract_hwid(payload: Any) -> str | None:
	for candidate in iter_identifier_candidates(payload):
		if HWID_PATTERN.match(candidate):
			return candidate
	return None


def discover_hwid(args: argparse.Namespace, authed_headers: dict[str, str]) -> tuple[str, str]:
	if args.hwid:
		return args.hwid, "manual-override"

	attempts: list[str] = []
	for name, url in (
		("account_info", "https://api.qendercore.com:8000/v1/s/accountinfo"),
		("dashboard_info", "https://api.qendercore.com:8000/v1/h/views/dashboard"),
	):
		status, response = run_curl_json(
			url=url,
			method="GET",
			headers=authed_headers,
			timeout=args.timeout,
		)

		hwid = extract_hwid(response)
		if status == 200 and hwid:
			return hwid, name

		if status != 200:
			attempts.append(f"{name}: HTTP {status}")
		else:
			attempts.append(f"{name}: HTTP 200 but no HWID-like field")

	raise RuntimeError(
		"Unable to discover HWID automatically. "
		+ "Tried: "
		+ "; ".join(attempts)
		+ ". Provide --hwid as a manual override."
	)


def simplify_sankey_stats(response: Any) -> list[dict[str, str]]:
	if not isinstance(response, dict):
		return []

	cols = response.get("cols")
	rows = response.get("rows")
	if not isinstance(cols, list) or not isinstance(rows, list) or not rows:
		return []

	first_row = rows[0]
	if not isinstance(first_row, list):
		return []

	slimmed: list[dict[str, str]] = []
	for index, col in enumerate(cols):
		if index >= len(first_row) or not isinstance(col, dict):
			continue
		label = col.get("label")
		if label not in SANKEY_LABELS:
			continue
		value = first_row[index]
		slimmed.append(
			{
				"name": label,
				"value": str(value),
			}
		)

	return slimmed


def simplify_pie_chart_stats(response: Any) -> list[dict[str, str]]:
	if not isinstance(response, dict):
		return []

	cols = response.get("cols")
	rows = response.get("rows")
	if not isinstance(cols, list) or not isinstance(rows, list) or not rows:
		return []

	first_row = rows[0]
	if not isinstance(first_row, list):
		return []

	slimmed: list[dict[str, str]] = []
	for index, col in enumerate(cols):
		if index >= len(first_row) or not isinstance(col, dict):
			continue
		label = col.get("label")
		if label not in PIE_CHART_LABELS:
			continue
		value = first_row[index]
		slimmed.append(
			{
				"name": label,
				"value": str(value),
			}
		)

	return slimmed


def simplify_graph_stats(response: Any) -> list[dict[str, Any]]:
	if not isinstance(response, dict):
		return []

	cols = response.get("cols")
	rows = response.get("rows")
	if not isinstance(cols, list) or not isinstance(rows, list):
		return []

	series: list[dict[str, Any]] = []
	metric_indexes: list[tuple[int, str]] = []
	for index, col in enumerate(cols):
		if not isinstance(col, dict):
			continue
		label = col.get("label")
		if label not in SANKEY_LABELS:
			continue
		metric_indexes.append((index, label))
		series.append({"name": label, "history": []})

	for row in rows:
		if not isinstance(row, list) or not row:
			continue
		ts = row[0]
		for series_idx, (col_idx, _) in enumerate(metric_indexes):
			if col_idx >= len(row):
				continue
			series[series_idx]["history"].append(
				{
					"time": str(ts),
					"value": str(row[col_idx]),
				}
			)

	return series


def fetch_sequence(args: argparse.Namespace) -> dict[str, Any]:
	headers = base_headers(args.client_seq)
	username, password = require_credentials(args)
	token = bearer_token(args, headers, username, password)

	authed_headers = dict(headers)
	authed_headers["authorization"] = f"bearer {token}"

	post_headers = dict(authed_headers)
	post_headers["Content-Type"] = "application/json"

	hwid, hwid_source = discover_hwid(args, authed_headers)

	results: dict[str, Any] = {
		"meta": {
			"hwid": hwid,
			"hwid_source": hwid_source,
			"exported_at": datetime.now(timezone.utc).isoformat(),
		},
	}

	status, response = run_curl_json(
		url="https://api.qendercore.com:8000/v1/h/ds",
		method="POST",
		headers=post_headers,
		timeout=args.timeout,
		json_body={
			"_ft": "hwm",
			"hwid": hwid,
			"props": [
				"inv.core.import_energy_delta_kwh",
				"inv.core.export_energy_delta_kwh",
				"inv.core.self_consumption_energy_delta_kwh",
			],
			"duration": "P1D",
			"resolution": "total",
			"tz": "local",
				"start": args.start_date,
		},
	)
	results["pie_chart_stats"] = {
		"status": status,
		"results": simplify_pie_chart_stats(response) if status == 200 else [],
	}

	status, response = run_curl_json(
		url="https://api.qendercore.com:8000/v1/h/ds",
		method="POST",
		headers=post_headers,
		timeout=args.timeout,
		json_body={
			"_ft": "hwm",
			"hwid": hwid,
			"props": [
				"inv.core.solar_prod_pwr_w",
				"inv.core.consumption_pwr_w",
				"inv.core.meter_pwr_w",
				"inv.core.battery_pwr_w",
			],
			"resolution": "PT15M",
			"tz": "local",
				"start": args.start_date,
		},
	)
	results["graph_stats"] = {
		"status": status,
		"results": simplify_graph_stats(response) if status == 200 else [],
	}

	status, response = run_curl_json(
		url="https://api.qendercore.com:8000/v1/h/ds",
		method="POST",
		headers=post_headers,
		timeout=args.timeout,
		json_body={
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
	)
	results["sankey_stats"] = {
		"status": status,
		"results": simplify_sankey_stats(response) if status == 200 else [],
	}

	return results


def save_output(path: Path, payload: dict[str, Any], pretty: bool) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8") as fh:
		if pretty:
			json.dump(payload, fh, indent=2, ensure_ascii=True)
			fh.write("\n")
		else:
			json.dump(payload, fh, separators=(",", ":"), ensure_ascii=True)


def main() -> int:
	args = parse_args()

	if load_dotenv is not None:
		load_dotenv()

	output_path = Path(args.output)

	try:
		results = fetch_sequence(args)
		save_output(output_path, results, pretty=args.pretty)
	except Exception as exc:
		print(f"Error: {exc}", file=sys.stderr)
		return 1

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
