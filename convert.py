#!/usr/bin/env python3
"""Convert a sing-box rule-set JSON file into a binary (.srs) rule-set.

Usage:
    python3 convert.py <rule-set.json> [--output-dir DIR] [--sing-box PATH]
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "sing-box-rulesets-binary"


def find_sing_box() -> str:
    path = shutil.which("sing-box")
    if path is None:
        raise FileNotFoundError(
            "sing-box binary not found in PATH; install it or pass --sing-box PATH"
        )
    return path


def validate_rule_set(json_path: Path) -> None:
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {json_path}: {e}") from e
    except OSError as e:
        raise FileNotFoundError(f"cannot read {json_path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"{json_path} must contain a JSON object")
    if not isinstance(data.get("rules"), list):
        raise ValueError(f"{json_path} must contain a 'rules' list")


def convert(json_path, output_dir=None, sing_box=None) -> Path:
    json_path = Path(json_path).resolve()
    if not json_path.is_file():
        raise FileNotFoundError(f"rule-set JSON file not found: {json_path}")

    validate_rule_set(json_path)

    if sing_box is None:
        sing_box = find_sing_box()

    output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{json_path.stem}.srs"

    cmd = [sing_box, "rule-set", "compile", str(json_path), "-o", str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(
            f"sing-box rule-set compile failed (exit {result.returncode})"
            + (f": {stderr}" if stderr else "")
        )

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(
            f"sing-box rule-set compile produced no output at {output_path}"
        )

    return output_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert a sing-box rule-set JSON file into a binary (.srs) rule-set."
    )
    parser.add_argument("json_file", help="path to the rule-set JSON file")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"directory for the output .srs file (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--sing-box",
        default=None,
        help="path to the sing-box binary (default: found in PATH)",
    )
    args = parser.parse_args(argv)

    try:
        output_path = convert(args.json_file, args.output_dir, args.sing_box)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
