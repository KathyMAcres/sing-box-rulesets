#!/usr/bin/env python3
"""Tests for update_gms.py."""

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import update_gms

CSV_OK = (
    "Icon,Name,Package,Genre\n"
    'https://icon/,Beta,"com.b.app","Tools"\n'
    'https://icon/,Alpha,"com.a.app","Tools"\n'
    'https://icon/,Alpha Dup,"com.a.app","Tools"\n'
    'https://icon/,Empty,"",""\n'
)


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body.encode("utf-8")


def write_fixture(path, package_ids, trailing_newline=True, extra=None):
    data = {
        "version": 4,
        "rules": [
            {"package_name": list(package_ids)},
            {"domain": ["example.com"]},
        ],
    }
    if extra:
        data.update(extra)
    text = json.dumps(data, indent=4)
    if trailing_newline:
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return text


class ParseTests(unittest.TestCase):
    def test_parse_ok(self):
        ids = update_gms.parse_package_ids(CSV_OK)
        self.assertEqual(ids, ["com.b.app", "com.a.app"])

    def test_parse_keeps_csv_order_and_dedupes(self):
        csv_text = (
            "Icon,Name,Package,Genre\n"
            'x,Z,"com.z.app",""\n'
            'x,A,"com.a.app",""\n'
            'x,Dup,"com.z.app",""\n'
        )
        ids = update_gms.parse_package_ids(csv_text)
        self.assertEqual(ids, ["com.z.app", "com.a.app"])

    def test_parse_missing_package_column(self):
        with self.assertRaises(update_gms.UpdateError):
            update_gms.parse_package_ids("Icon,Name\nx,y\n")

    def test_parse_no_ids(self):
        with self.assertRaises(update_gms.UpdateError):
            update_gms.parse_package_ids("Icon,Name,Package,Genre\n")

    def test_parse_not_csv(self):
        with self.assertRaises(update_gms.UpdateError):
            update_gms.parse_package_ids("not,a,csv")


class FetchTests(unittest.TestCase):
    def test_fetch_ok(self):
        with mock.patch.object(
            update_gms.urllib.request, "urlopen", return_value=FakeResponse(CSV_OK)
        ) as m:
            ids = update_gms.fetch_package_ids("http://example.com/list.csv")
        m.assert_called_once_with("http://example.com/list.csv", timeout=30)
        self.assertEqual(ids, ["com.b.app", "com.a.app"])

    def test_fetch_url_error(self):
        with mock.patch.object(
            update_gms.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError("down"),
        ):
            with self.assertRaises(update_gms.UpdateError):
                update_gms.fetch_package_ids("http://example.com/list.csv")


class UpdateTests(unittest.TestCase):
    def test_update_only_changes_package_name_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            original = write_fixture(path, ["com.old.one", "com.old.two"])
            count = update_gms.update(path, ["com.new.b", "com.new.a", "com.new.b"])

            self.assertEqual(count, 2)
            new_text = path.read_text(encoding="utf-8")
            data = json.loads(new_text)
            self.assertEqual(data["rules"][0]["package_name"], ["com.new.b", "com.new.a"])
            self.assertEqual(data["rules"][1], {"domain": ["example.com"]})
            self.assertEqual(data["version"], 4)
            self.assertNotEqual(new_text, original)
            # Byte-for-byte check: file equals original with only the array replaced.
            expected_data = json.loads(original)
            expected_data["rules"][0]["package_name"] = ["com.new.b", "com.new.a"]
            expected_text = json.dumps(expected_data, indent=4) + "\n"
            self.assertEqual(new_text, expected_text)

    def test_update_preserves_trailing_newline_presence(self):
        with tempfile.TemporaryDirectory() as tmp:
            for trailing in (True, False):
                path = Path(tmp) / f"rules_{trailing}.json"
                write_fixture(path, ["com.old"], trailing_newline=trailing)
                update_gms.update(path, ["com.new"])
                self.assertEqual(path.read_text(encoding="utf-8").endswith("\n"), trailing)

    def test_update_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(update_gms.UpdateError):
                update_gms.update(Path(tmp) / "nope.json", ["com.a"])

    def test_update_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{nope", encoding="utf-8")
            with self.assertRaises(update_gms.UpdateError):
                update_gms.update(path, ["com.a"])

    def test_update_missing_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "norules.json"
            path.write_text(json.dumps({"version": 4}), encoding="utf-8")
            with self.assertRaises(update_gms.UpdateError):
                update_gms.update(path, ["com.a"])

    def test_update_package_name_not_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notlist.json"
            path.write_text(
                json.dumps({"version": 4, "rules": [{"package_name": "com.a"}]}),
                encoding="utf-8",
            )
            with self.assertRaises(update_gms.UpdateError):
                update_gms.update(path, ["com.a"])

    def test_update_rules_not_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "noruleslist.json"
            path.write_text(json.dumps({"version": 4, "rules": {}}), encoding="utf-8")
            with self.assertRaises(update_gms.UpdateError):
                update_gms.update(path, ["com.a"])


class MainTests(unittest.TestCase):
    def test_main_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            write_fixture(path, ["com.old"])
            with mock.patch.object(
                update_gms.urllib.request,
                "urlopen",
                return_value=FakeResponse(CSV_OK),
            ):
                rc = update_gms.main([str(path), "--url", "http://example.com/list.csv"])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(path.read_text())["rules"][0]["package_name"],
                             ["com.b.app", "com.a.app"])

    def test_main_default_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "google-apps.json"
            write_fixture(path, ["com.old"])
            with mock.patch.object(update_gms, "DEFAULT_JSON", path):
                with mock.patch.object(
                    update_gms.urllib.request,
                    "urlopen",
                    return_value=FakeResponse(CSV_OK),
                ):
                    rc = update_gms.main([])
            self.assertEqual(rc, 0)
            self.assertTrue(path.exists())

    def test_main_fetch_error_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            write_fixture(path, ["com.old"])
            with mock.patch.object(
                update_gms.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("down"),
            ):
                rc = update_gms.main([str(path), "--url", "http://example.com/list.csv"])
            self.assertEqual(rc, 1)
            self.assertEqual(json.loads(path.read_text())["rules"][0]["package_name"],
                             ["com.old"])


if __name__ == "__main__":
    unittest.main()