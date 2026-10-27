#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import patch, MagicMock
import json
import os
import sys

# Windows 終端機 UTF-8 強制重設
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import monitor

class TestMonitorLogic(unittest.TestCase):

    def test_strict_200_evaluation(self):
        target = {
            "name": "Aime 服務平台",
            "url": "https://my-aime.net/",
            "strict_200": True
        }

        # 模擬 200 (在線)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.reason = "OK"
        with patch("urllib.request.build_opener") as mock_opener:
            mock_inst = MagicMock()
            mock_inst.open.return_value.__enter__.return_value = mock_resp
            mock_opener.return_value = mock_inst
            res = monitor.check_target(target)
            self.assertTrue(res["is_online"])
            self.assertEqual(res["status_code"], 200)

        # 模擬 403 (離線)
        import urllib.error
        http_err = urllib.error.HTTPError("https://my-aime.net/", 403, "Forbidden", {}, None)
        with patch("urllib.request.build_opener") as mock_opener:
            mock_inst = MagicMock()
            mock_inst.open.side_effect = http_err
            mock_opener.return_value = mock_inst
            res = monitor.check_target(target)
            self.assertFalse(res["is_online"])
            self.assertEqual(res["status_code"], 403)

    def test_normal_target_evaluation(self):
        target = {
            "name": "maimai (日本官方網站)",
            "url": "https://maimai.sega.jp/",
            "strict_200": False
        }

        # 模擬 200 -> 在線
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.reason = "OK"
        with patch("urllib.request.build_opener") as mock_opener:
            mock_inst = MagicMock()
            mock_inst.open.return_value.__enter__.return_value = mock_resp
            mock_opener.return_value = mock_inst
            res = monitor.check_target(target)
            self.assertTrue(res["is_online"])

        # 模擬 503 維護中 -> 離線
        import urllib.error
        http_err = urllib.error.HTTPError("https://maimai.sega.jp/", 503, "Service Unavailable", {}, None)
        with patch("urllib.request.build_opener") as mock_opener:
            mock_inst = MagicMock()
            mock_inst.open.side_effect = http_err
            mock_opener.return_value = mock_inst
            res = monitor.check_target(target)
            self.assertFalse(res["is_online"])

    def test_build_discord_embed_categories(self):
        results = [
            {
                "url": "https://url1",
                "name": "NET 服務1",
                "category": "🎮 玩家數據服務 (NET)",
                "is_online": True,
                "status_code": 200,
                "reason": "OK",
                "elapsed_ms": 120
            },
            {
                "url": "https://url2",
                "name": "NET 服務2",
                "category": "🎮 玩家數據服務 (NET)",
                "is_online": False,
                "status_code": 503,
                "reason": "Maintenance",
                "elapsed_ms": 80
            },
            {
                "url": "https://url3",
                "name": "Aime 平台",
                "category": "🪪 帳號與認證系統 (Aime)",
                "is_online": False,
                "status_code": 403,
                "reason": "Forbidden",
                "elapsed_ms": 60
            }
        ]
        changed_urls = {"https://url2"}

        embed = monitor.build_discord_embed(results, changed_urls, report_type="status_change")

        # 檢查標題與動態條
        self.assertIn("ALL.Net", embed["title"])
        self.assertIn("▰", embed["description"])
        self.assertIn("本次狀態異動", embed["description"])

        # 檢查分類分組 fields (應有 2 個分類群組)
        self.assertEqual(len(embed["fields"]), 2)
        cat_names = [f["name"] for f in embed["fields"]]
        self.assertTrue(any("玩家數據服務" in c for c in cat_names))
        self.assertTrue(any("帳號與認證系統" in c for c in cat_names))

        # 檢查已更新標籤
        self.assertIn("[已更新]", embed["fields"][0]["value"])

    def test_downward_compatible_load_state(self):
        legacy_data = {
            "https://url1": {"is_online": True, "status_code": 200}
        }
        with patch("os.path.isfile", return_value=True), \
             patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(legacy_data))):
            loaded = monitor.load_state()
            self.assertIn("urls", loaded)
            self.assertIn("https://url1", loaded["urls"])

    def test_error_type_classification(self):
        # 測試 403 存取受限
        import urllib.error
        target_403 = {"name": "Test 403", "url": "https://test403", "strict_200": False}
        with patch("urllib.request.build_opener") as mock_opener:
            mock_inst = MagicMock()
            mock_inst.open.side_effect = urllib.error.HTTPError("https://test403", 403, "Forbidden", {}, None)
            mock_opener.return_value = mock_inst
            res = monitor.check_target(target_403)
            self.assertEqual(res["error_type"], "access_denied")
            self.assertIn("限制存取", res["error_detail"])

        # 測試 503 維護
        target_503 = {"name": "Test 503", "url": "https://test503", "strict_200": False}
        with patch("urllib.request.build_opener") as mock_opener:
            mock_inst = MagicMock()
            mock_inst.open.side_effect = urllib.error.HTTPError("https://test503", 503, "Service Unavailable", {}, None)
            mock_opener.return_value = mock_inst
            res = monitor.check_target(target_503)
            self.assertEqual(res["error_type"], "maintenance")
            self.assertIn("維護中", res["error_detail"])

    def test_export_status_json_with_diagnostics(self):
        results = [
            {
                "url": "https://sample.url",
                "name": "Sample Node",
                "category": "NET",
                "is_online": True,
                "status_code": 200,
                "reason": "OK",
                "elapsed_ms": 100,
                "checked_at": "2026-10-27T00:00:00Z",
                "error_type": "ok",
                "error_detail": "服務正常回應"
            }
        ]
        state = {
            "history": {
                "https://sample.url": [{"t": 100, "ms": 100, "ok": True, "code": 200}]
            },
            "diagnostics": {
                "https://sample.url": {
                    "last_success_at": "2026-10-27T00:00:00Z",
                    "last_failure_at": None,
                    "consecutive_failures": 0,
                    "recent_uptime_percent": 100.0,
                    "sample_count": 1
                }
            }
        }
        written_data = None
        def mock_json_dump(obj, f, **kwargs):
            nonlocal written_data
            written_data = obj

        with patch("builtins.open", unittest.mock.mock_open()), \
             patch("json.dump", side_effect=mock_json_dump):
            monitor.export_status_json(results, state=state)
            self.assertIsNotNone(written_data)
            self.assertIn("current_availability_percent", written_data["summary"])
            self.assertIn("historical_uptime_percent", written_data["summary"])
            self.assertEqual(written_data["services"][0]["diagnostics"]["probe_type"], "HTTP/HTTPS 標頭探測")

if __name__ == "__main__":
    unittest.main()
