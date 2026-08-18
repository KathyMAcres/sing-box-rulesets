#!/usr/bin/env python3
"""Fetch GMS app package ids from a CSV and update rules[0].package_name in a
sing-box rule-set JSON file.

Only the rules[0].package_name array is changed; every other part of the file is
preserved byte-for-byte.

Usage:
    python3 update_gms.py [json_file] [--url CSV_URL]
"""

import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://github.com/petarov/google-android-app-ids/raw/refs/heads/master/"
    "dist/google-app-ids.csv"
)
DEFAULT_JSON = Path(__file__).resolve().parent / "google-apps.json"


class UpdateError(Exception):
    """Raised when the update cannot be completed."""


def parse_package_ids(csv_text):
    """Return a unique list of package ids from the CSV 'Package' column, keeping
    the order in which they appear in the CSV."""
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
    except csv.Error as e:
        raise UpdateError(f"failed to parse CSV: {e}") from e

    if "Package" not in (reader.fieldnames or []):
        raise UpdateError("unexpected CSV format: missing 'Package' column")

    ids = []
    try:
        for row in reader:
            value = row.get("Package")
            if value:
                ids.append(value.strip())
    except csv.Error as e:
        raise UpdateError(f"failed to parse CSV: {e}") from e

    ids = list(dict.fromkeys(ids))
    if not ids:
        raise UpdateError("no package ids found in CSV")
    return ids


def fetch_package_ids(url=SOURCE_URL, timeout=30):
    """Download the CSV from url and return the sorted list of package ids."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
    except UnicodeDecodeError as e:
        raise UpdateError(f"failed to decode response from {url}: {e}") from e
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError(f"failed to fetch {url}: {e}") from e
    return parse_package_ids(text)


def update(json_path, package_ids):
    """Replace rules[0].package_name in json_path with package_ids.

    Everything else in the file (keys, ordering, trailing newline) is preserved.
    """
    json_path = Path(json_path).resolve()
    if not json_path.is_file():
        raise UpdateError(f"rule-set JSON file not found: {json_path}")

    try:
        text = json_path.read_text(encoding="utf-8")
    except OSError as e:
        raise UpdateError(f"cannot read {json_path}: {e}") from e

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise UpdateError(f"invalid JSON in {json_path}: {e}") from e

    if not isinstance(data, dict):
        raise UpdateError(f"{json_path} must contain a JSON object")
    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        raise UpdateError(f"{json_path} must contain a non-empty 'rules' list")
    first = rules[0]
    if not isinstance(first, dict) or not isinstance(first.get("package_name"), list):
        raise UpdateError(f"{json_path} rules[0].package_name must be a list")

    first["package_name"] = list(dict.fromkeys(package_ids))

    new_text = json.dumps(data, indent=4)
    if text.endswith("\n"):
        new_text += "\n"

    try:
        json_path.write_text(new_text, encoding="utf-8")
    except OSError as e:
        raise UpdateError(f"cannot write {json_path}: {e}") from e

    return len(first["package_name"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Update rules[0].package_name in a sing-box rule-set JSON file with "
            "GMS app package ids fetched from a CSV."
        )
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default=str(DEFAULT_JSON),
        help=f"path to the rule-set JSON file (default: {DEFAULT_JSON})",
    )
    parser.add_argument(
        "--url",
        default=SOURCE_URL,
        help=f"CSV source URL (default: {SOURCE_URL})",
    )
    parser.add_argument("--timeout", type=float, default=30, help="fetch timeout in seconds")
    args = parser.parse_args(argv)

    try:
        ids = fetch_package_ids(args.url, args.timeout)
        count = update(args.json_file, ids)
    except UpdateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(
        f"updated rules[0].package_name with {count} package ids in "
        f"{Path(args.json_file).resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())