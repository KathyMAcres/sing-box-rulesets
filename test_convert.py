#!/usr/bin/env python3
"""Tests for convert.py."""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import convert

REPO_DIR = Path(__file__).resolve().parent
SAMPLE_JSON = REPO_DIR / "google-apps.json"


class ConvertTests(unittest.TestCase):
    def test_default_output_dir(self):
        self.assertEqual(convert.DEFAULT_OUTPUT_DIR, REPO_DIR.parent / "sing-box-rulesets-binary")

    def test_convert_real_ruleset(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = convert.convert(SAMPLE_JSON, tmp)
            expected = (Path(tmp) / "google-apps.srs").resolve()
            self.assertEqual(out, expected)
            self.assertTrue(expected.is_file())
            self.assertGreater(expected.stat().st_size, 0)

    def test_output_name_uses_source_stem(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "custom-name.json"
            src.write_text(
                json.dumps({"version": 4, "rules": [{"package_name": ["com.example.app"]}]}),
                encoding="utf-8",
            )
            out = convert.convert(src, tmp)
            self.assertEqual(out.name, "custom-name.srs")

    def test_missing_input_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.json"
            with self.assertRaises(FileNotFoundError):
                convert.convert(missing, tmp)

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(ValueError):
                convert.convert(bad, tmp)

    def test_missing_rules_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "norules.json"
            bad.write_text(json.dumps({"version": 4}), encoding="utf-8")
            with self.assertRaises(ValueError):
                convert.convert(bad, tmp)

    def test_sing_box_not_found(self):
        with mock.patch.object(convert.shutil, "which", return_value=None):
            with tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / "input.json"
                src.write_text(
                    json.dumps({"version": 4, "rules": [{"domain": ["example.com"]}]}),
                    encoding="utf-8",
                )
                with self.assertRaises(FileNotFoundError):
                    convert.convert(src, tmp)

    def test_compile_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            failing = Path(tmp) / "failing-sing-box"
            failing.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            failing.chmod(0o755)
            src = Path(tmp) / "input.json"
            src.write_text(
                json.dumps({"version": 4, "rules": [{"domain": ["example.com"]}]}),
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                convert.convert(src, tmp, sing_box=str(failing))

    def test_convert_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "a" / "b"
            out = convert.convert(SAMPLE_JSON, nested)
            self.assertTrue(out.is_file())

    def test_main_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = convert.main([str(SAMPLE_JSON), "--output-dir", tmp])
            self.assertEqual(rc, 0)

    def test_main_missing_input_returns_1(self):
        rc = convert.main(["/no/such/file.json"])
        self.assertEqual(rc, 1)

    def test_main_invalid_json_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("not json", encoding="utf-8")
            rc = convert.main([str(bad), "--output-dir", tmp])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
