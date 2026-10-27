#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import uuid
import argparse
import subprocess
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# Windows 終端機 UTF-8 強制重設
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")
STATUS_JSON_FILE = os.path.join(BASE_DIR, "status.json")
LOGO_FILE = os.path.join(BASE_DIR, "assets", "logo.png")

DEFAULT_TARGETS = [
    {
        "name": "maimai DX (國際版 NET)",
        "url": "https://maimaidx-eng.com/",
        "category": "🎮 玩家數據服務 (NET)",
        "strict_200": False
    },
    {
        "name": "maimai DX (日本版 NET)",
        "url": "https://maimaidx.jp/",
        "category": "🎮 玩家數據服務 (NET)",
        "strict_200": False
    },
    {
        "name": "CHUNITHM-NET (日本版)",
        "url": "https://new.chunithm-net.com/",
        "category": "🎮 玩家數據服務 (NET)",
        "strict_200": False
    },
    {
        "name": "CHUNITHM-NET (國際版)",
        "url": "https://chunithm-net-eng.com/",
        "category": "🎮 玩家數據服務 (NET)",
        "strict_200": False
    },
    {
        "name": "O.N.G.E.K.I. (音擊 NET)",
        "url": "https://ongeki-net.com/",
        "category": "🎮 玩家數據服務 (NET)",
        "strict_200": False
    },
    {
        "name": "Aime 服務平台 (my-aime)",
        "url": "https://my-aime.net/",
        "category": "🪪 帳號與認證系統 (Aime)",
        "strict_200": True
    },
    {
        "name": "maimai (日本官方網站)",
        "url": "https://maimai.sega.jp/",
        "category": "🌐 遊戲官方網站 (Web)",
        "strict_200": False
    },
    {
        "name": "maimai (國際官方網站)",
        "url": "https://maimai.sega.com/",
        "category": "🌐 遊戲官方網站 (Web)",
        "strict_200": False
    },
    {
        "name": "CHUNITHM (國際官方網站)",
        "url": "https://chunithm.sega.com/",
        "category": "🌐 遊戲官方網站 (Web)",
        "strict_200": False
    },
    {
        "name": "CHUNITHM (日本官方網站)",
        "url": "https://chunithm.sega.jp/",
        "category": "🌐 遊戲官方網站 (Web)",
        "strict_200": False
    },
    {
        "name": "O.N.G.E.K.I. (日本官方網站)",
        "url": "https://ongeki.sega.jp/",
        "category": "🌐 遊戲官方網站 (Web)",
        "strict_200": False
    }
]

def load_dotenv():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            clean = line.strip()
            if not clean or clean.startswith("#") or "=" not in clean:
                continue
            k, v = clean.split("=", 1)
            k = k.strip()
            v = v.strip().strip("\"'")
            if k not in os.environ:
                os.environ[k] = v

def load_config():
    load_dotenv()
    config = {
        "discord_webhook_url": os.getenv("DISCORD_WEBHOOK_URL", ""),
        "check_interval_seconds": int(os.getenv("CHECK_INTERVAL_SECONDS", 60)),
        "timeout_seconds": 10,
        "proxy": os.getenv("HTTP_PROXY", None) or os.getenv("HTTPS_PROXY", None),
        "send_on_startup": True,
        "daily_report_enabled": True,
        "daily_report_time": "09:00",
        "targets": DEFAULT_TARGETS
    }

    env_webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                if file_config.get("discord_webhook_url") and not env_webhook:
                    config["discord_webhook_url"] = file_config["discord_webhook_url"]
                if "check_interval_seconds" in file_config:
                    config["check_interval_seconds"] = file_config["check_interval_seconds"]
                if "timeout_seconds" in file_config:
                    config["timeout_seconds"] = file_config["timeout_seconds"]
                if "proxy" in file_config:
                    config["proxy"] = file_config["proxy"]
                if "send_on_startup" in file_config:
                    config["send_on_startup"] = file_config["send_on_startup"]
                if "daily_report_enabled" in file_config:
                    config["daily_report_enabled"] = file_config["daily_report_enabled"]
                if "daily_report_time" in file_config:
                    config["daily_report_time"] = file_config["daily_report_time"]
                if file_config.get("targets"):
                    config["targets"] = file_config["targets"]
        except Exception as e:
            print(f"[警告] 讀取 config.json 發生錯誤: {e}，將使用預設設定", flush=True)

    return config

def load_state():
    if not os.path.isfile(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if not isinstance(raw, dict):
                return None
            if "urls" not in raw:
                raw = {
                    "last_daily_report_date": None,
                    "urls": raw,
                    "history": {},
                    "diagnostics": {}
                }
            if "history" not in raw:
                raw["history"] = {}
            if "diagnostics" not in raw:
                raw["diagnostics"] = {}
            return raw
    except Exception as e:
        print(f"[警告] 讀取 state.json 發生錯誤: {e}", flush=True)
        return None

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[錯誤] 儲存 state.json 失敗: {e}", flush=True)

def export_status_json(results, state=None):
    total = len(results)
    online_count = sum(1 for r in results if r.get("is_online", False))
    offline_count = total - online_count
    pct = round((online_count / total) * 100, 1) if total > 0 else 0.0

    hist_map = (state.get("history") or {}) if state else {}
    diag_map = (state.get("diagnostics") or {}) if state else {}

    enriched_services = []
    for r in results:
        url = r["url"]
        enriched = dict(r)
        enriched["history"] = hist_map.get(url, [])
        enriched["diagnostics"] = diag_map.get(url, {
            "last_success_at": r["checked_at"] if r["is_online"] else None,
            "last_failure_at": r["checked_at"] if not r["is_online"] else None,
            "consecutive_failures": 0 if r["is_online"] else 1,
            "sample_count": len(enriched["history"]),
            "recent_uptime_percent": 100.0 if r["is_online"] else 0.0
        })
        enriched_services.append(enriched)

    data = {
        "system_name": "ALL.Net Sentinel Telemetry",
        "version": "2.1.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total,
            "online": online_count,
            "offline": offline_count,
            "uptime_percent": pct,
            "status_text": "全數在線" if online_count == total else ("全數離線" if online_count == 0 else f"{offline_count} 個節點異常")
        },
        "services": enriched_services
    }

    try:
        with open(STATUS_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] 匯出 status.json 失敗: {e}", flush=True)

def git_push_status():
    try:
        subprocess.run(["git", "add", "status.json"], cwd=BASE_DIR, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        diff_res = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=BASE_DIR)
        if diff_res.returncode != 0:
            subprocess.run(["git", "commit", "-m", "chore(telemetry): 自動更新 ALL.Net 服務狀態快照 [skip ci]"], cwd=BASE_DIR, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "push"], cwd=BASE_DIR, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[Git] 已成功自動推送最新狀態快照至 GitHub Pages！", flush=True)
        else:
            print("[Git] 狀態快照無變更，跳過推送。", flush=True)
    except Exception as e:
        print(f"[警告] Git 自動推送失敗: {e}", flush=True)

def check_target(target, timeout=10, proxy=None):
    url = target["url"]
    strict_200 = target.get("strict_200", False)
    category = target.get("category", "🌐 其他站點")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,zh-TW;q=0.7",
    }

    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    handlers.append(urllib.request.HTTPSHandler(context=ssl_context))

    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers=headers)

    start_time = time.time()
    try:
        with opener.open(req, timeout=timeout) as resp:
            elapsed_ms = int((time.time() - start_time) * 1000)
            status_code = resp.status
            reason = resp.reason if hasattr(resp, "reason") else "OK"
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        status_code = e.code
        reason = e.reason if hasattr(e, "reason") else "HTTP Error"
    except urllib.error.URLError as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        status_code = 0
        reason = f"連線失敗 ({e.reason})"
    except TimeoutError:
        elapsed_ms = int((time.time() - start_time) * 1000)
        status_code = 0
        reason = "連線超時"
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        status_code = 0
        reason = f"異常 ({type(e).__name__})"

    if strict_200:
        is_online = (status_code == 200)
    else:
        is_online = (200 <= status_code < 400)

    # 精細分類異常原因
    raw_r = str(reason).lower()
    if is_online:
        error_type = "ok"
        error_detail = "服務正常回應"
    elif status_code == 403:
        error_type = "access_denied"
        error_detail = "伺服器拒絕或限制存取 (可能受限於日本地區 IP、認證限制或 WAF 防護)"
    elif status_code == 503:
        error_type = "maintenance"
        error_detail = "伺服器回報服務維護中 (Service Temporarily Unavailable)"
    elif 400 <= status_code < 500:
        error_type = "client_error"
        error_detail = f"客戶端請求錯誤 (HTTP {status_code})"
    elif status_code >= 500:
        error_type = "server_error"
        error_detail = f"目標伺服器內部錯誤 (HTTP {status_code})"
    elif "timeout" in raw_r or "超時" in raw_r or "timed out" in raw_r:
        error_type = "timeout"
        error_detail = "連線逾時：探測端在預設期限內未收到伺服器回應"
    elif "10061" in raw_r or "refused" in raw_r or "拒絕" in raw_r:
        error_type = "conn_refused"
        error_detail = "連線被拒：目標伺服器主動拒絕連線 (連接埠未開放或防火牆阻斷)"
    elif "getaddrinfo" in raw_r or "name resolution" in raw_r or "dns" in raw_r:
        error_type = "dns_error"
        error_detail = "網域名稱解析失敗 (DNS 解析異常)"
    else:
        error_type = "network_error"
        error_detail = f"網路連線異常 ({reason})"

    return {
        "url": url,
        "name": target.get("name", url),
        "category": category,
        "strict_200": strict_200,
        "is_online": is_online,
        "status_code": status_code,
        "reason": reason,
        "elapsed_ms": elapsed_ms,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_detail": error_detail
    }

def format_status_badge(item):
    """
    將狀態碼與錯誤原因格式化為專業精簡的狀態標籤，去除冗長的系統錯誤字串
    """
    code = item.get("status_code", 0)
    raw_reason = str(item.get("reason", ""))
    url = item.get("url", "")

    if item.get("is_online", False):
        delay = f" · {item['elapsed_ms']}ms" if item.get("elapsed_ms", 0) > 0 else ""
        return f"`200 · 正常`{delay}"

    # 離線情境清洗
    if code == 503:
        return "`503 · 維護中 (Service Unavailable)`"
    if code == 403:
        if "my-aime" in url or item.get("strict_200", False):
            return "`403 · 日本限定阻斷 (Japan Only)`"
        return "`403 · 拒絕存取 (Forbidden)`"
    if code == 404:
        return "`404 · 找不到頁面`"
    if code > 0:
        return f"`HTTP {code} 異常`"

    # 網路底層連線異常清洗
    if "10061" in raw_reason or "refused" in raw_reason.lower() or "拒絕" in raw_reason:
        return "`連線被拒 (Connection Refused)`"
    if "timeout" in raw_reason.lower() or "超時" in raw_reason or "timed out" in raw_reason.lower():
        return "`連線逾時 (Timeout)`"
    if "getaddrinfo" in raw_reason.lower() or "name resolution" in raw_reason.lower():
        return "`網域解析失敗 (DNS Error)`"

    return "`無法建立連線`"

def build_discord_embed(results, changed_urls, report_type="status_change"):
    """
    建構現代化、資訊密集且具備結構化分組之 Discord Rich Embed
    """
    total = len(results)
    online_count = sum(1 for r in results if r["is_online"])
    offline_count = total - online_count
    pct = int((online_count / total) * 100) if total > 0 else 0

    # 視覺化動態進度條 (▰▱)
    filled_bars = int(round((online_count / total) * 10)) if total > 0 else 0
    progress_bar = "▰" * filled_bars + "▱" * (10 - filled_bars)

    now_unix = int(time.time())

    # 動態主題配色與標題
    if report_type == "status_change":
        title = "🚨 ALL.Net | 服務狀態異動通知"
        color = 0xED4245 if offline_count > 0 else 0x57F287  # 若全修復則呈現勝利綠，否則紅
    elif report_type == "daily":
        title = "📊 ALL.Net | 每日例行監控摘要"
        color = 0x5865F2  # Discord Blurple 皇家藍
    elif report_type == "startup":
        title = "🟦 ALL.Net | 監控系統已啟動 (初始基準)"
        color = 0x3498DB  # 天藍色
    else:
        title = "🛰️ ALL.Net | 即時狀態報告"
        color = 0x2ECC71 if online_count == total else 0xF1C40F

    # 整體狀態描述文字
    if online_count == total:
        overall_status = "🟢 **全數服務在線 (Operational)**"
    elif online_count == 0:
        overall_status = "🔴 **全數服務離線 (Major Outage)**"
    else:
        overall_status = f"⚠️ **部分服務異常 ({offline_count} 個離線)**"

    description_lines = [
        f"> **系統整體概況**：{overall_status}",
        f"> **服務在線可用率**：`{online_count}/{total} 在線 ({pct}%)` {progress_bar}",
        f"> **最後檢測時間**：<t:{now_unix}:T> (<t:{now_unix}:R>)",
        ""
    ]

    # 若有站點異動，頂部特別建立「最新異動 (Status Changes)」醒目區塊
    if changed_urls:
        description_lines.append("### 🔔 本次狀態異動 (Recent Changes)")
        for r in results:
            if r["url"] in changed_urls:
                from_icon = "🔴" if r["is_online"] else "🟢"
                to_icon = "🟢" if r["is_online"] else "🔴"
                badge_desc = format_status_badge(r)
                description_lines.append(
                    f"• {from_icon} ➔ {to_icon} **[{r['name']}]({r['url']})** ({badge_desc})"
                )
        description_lines.append("")

    # 依業務類別分組聚合成結構化欄位 (Fields)
    categorized = {}
    for r in results:
        cat = r.get("category", "🌐 其他站點")
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(r)

    fields = []
    for cat_name, items in categorized.items():
        cat_lines = []
        for item in items:
            status_icon = "🟢" if item["is_online"] else "🔴"
            badge = " 🔄 **[已更新]**" if item["url"] in changed_urls else ""
            status_desc = format_status_badge(item)

            cat_lines.append(
                f"{status_icon} **[{item['name']}]({item['url']})**\n"
                f"└ {status_desc}{badge}"
            )

        fields.append({
            "name": f"{cat_name} · {len(items)} 項",
            "value": "\n".join(cat_lines),
            "inline": False
        })

    embed = {
        "title": title,
        "description": "\n".join(description_lines).strip(),
        "color": color,
        "fields": fields,
        "footer": {
            "text": "ALL.Net Status Sentinel • 每 60 秒自動巡檢"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if os.path.isfile(LOGO_FILE):
        embed["author"] = {
            "name": "ALL.Net 服務監控中樞",
            "icon_url": "attachment://logo.png"
        }
        embed["thumbnail"] = {
            "url": "attachment://logo.png"
        }

    return embed

def send_discord_webhook(webhook_url, embed, dry_run=False):
    has_logo = os.path.isfile(LOGO_FILE)
    if dry_run:
        print("[Dry-Run] 模擬發送 Discord Webhook：", flush=True)
        print(f"[Dry-Run] 專屬 Logo 存在: {'是 (' + LOGO_FILE + ')' if has_logo else '否'}", flush=True)
        print(json.dumps(embed, ensure_ascii=False, indent=2), flush=True)
        return True

    if not webhook_url or not webhook_url.startswith("https://discord.com/api/webhooks/"):
        print(f"[錯誤] 未設定有效之 DISCORD_WEBHOOK_URL: {webhook_url}", flush=True)
        return False

    payload = {
        "username": "ALL.Net Service Monitor",
        "embeds": [embed]
    }

    if has_logo:
        payload["attachments"] = [{"id": 0, "filename": "logo.png"}]
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        try:
            with open(LOGO_FILE, "rb") as f:
                logo_bytes = f.read()

            parts = [
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\nContent-Type: application/json; charset=utf-8\r\n\r\n{json.dumps(payload, ensure_ascii=False)}\r\n".encode("utf-8"),
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"files[0]\"; filename=\"logo.png\"\r\nContent-Type: image/png\r\n\r\n".encode("utf-8") + logo_bytes + b"\r\n",
                f"--{boundary}--\r\n".encode("utf-8")
            ]
            body = b"".join(parts)
            headers = {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "ALLNetDiscordWebhook/1.0"
            }
        except Exception as e:
            print(f"[警告] 讀取 logo.png 失敗，將轉為純文字發送: {e}", flush=True)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "ALLNetDiscordWebhook/1.0"
            }
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "ALLNetDiscordWebhook/1.0"
        }

    req = urllib.request.Request(webhook_url, data=body, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                print(f"[Webhook] 成功送出 Discord 通知 (HTTP {resp.status})", flush=True)
                return True
            else:
                print(f"[Webhook] 送出通知收到非常規狀態碼: {resp.status}", flush=True)
                return False
    except urllib.error.HTTPError as e:
        print(f"[Webhook 失敗] HTTPError {e.code}: {e.read().decode('utf-8', errors='ignore')}", flush=True)
        return False
    except Exception as e:
        print(f"[Webhook 失敗] 發生錯誤: {e}", flush=True)
        return False

def run_check_cycle(config, current_state, dry_run=False, force_send=False, auto_push=False):
    targets = config["targets"]
    timeout = config["timeout_seconds"]
    proxy = config["proxy"]
    webhook_url = config["discord_webhook_url"]
    send_on_startup = config["send_on_startup"]
    daily_report_enabled = config.get("daily_report_enabled", True)
    daily_report_time = config.get("daily_report_time", "09:00")

    today_str = datetime.now().strftime("%Y-%m-%d")
    now_time_str = datetime.now().strftime("%H:%M")
    now_iso = datetime.now(timezone.utc).isoformat()
    now_unix = int(time.time())

    is_startup = (current_state is None)
    prev_urls_state = {}
    prev_history = {}
    prev_diagnostics = {}
    last_daily_report_date = None

    if current_state is not None:
        prev_urls_state = current_state.get("urls", {})
        prev_history = current_state.get("history", {})
        prev_diagnostics = current_state.get("diagnostics", {})
        last_daily_report_date = current_state.get("last_daily_report_date")

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 開始執行服務狀態平行檢測 (共 {len(targets)} 個目標)...", flush=True)

    current_results = [None] * len(targets)
    start_all = time.time()

    with ThreadPoolExecutor(max_workers=min(12, len(targets))) as executor:
        future_to_idx = {
            executor.submit(check_target, target, timeout=timeout, proxy=proxy): idx
            for idx, target in enumerate(targets)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                res = future.result()
            except Exception as e:
                target = targets[idx]
                res = {
                    "url": target["url"],
                    "name": target.get("name", target["url"]),
                    "category": target.get("category", "🌐 其他站點"),
                    "strict_200": target.get("strict_200", False),
                    "is_online": False,
                    "status_code": 0,
                    "reason": f"探測異常 ({e})",
                    "elapsed_ms": 0,
                    "checked_at": now_iso,
                    "error_type": "unknown",
                    "error_detail": f"探測程序發生未知例外: {e}"
                }
            current_results[idx] = res

    elapsed_all = round(time.time() - start_all, 2)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 平行檢測完成！耗時 {elapsed_all} 秒", flush=True)

    new_urls_state = {}
    new_history = dict(prev_history)
    new_diagnostics = dict(prev_diagnostics)
    changed_urls = set()

    for idx, res in enumerate(current_results, 1):
        url = res["url"]
        name = res["name"]
        status_str = "🟢 在線" if res["is_online"] else "🔴 離線"
        print(f"  [{idx:02d}/{len(targets):02d}] {name} -> {status_str} (狀態碼: {res['status_code']} | 耗時: {res['elapsed_ms']}ms)", flush=True)

        new_urls_state[url] = {
            "is_online": res["is_online"],
            "status_code": res["status_code"],
            "reason": res["reason"],
            "checked_at": res["checked_at"]
        }

        # 維護歷史數據 (保留最近 60 筆)
        hist = list(new_history.get(url, []))
        hist.append({
            "t": now_unix,
            "ms": res["elapsed_ms"],
            "ok": res["is_online"],
            "code": res["status_code"]
        })
        if len(hist) > 60:
            hist = hist[-60:]
        new_history[url] = hist

        # 維護診斷統計
        diag = dict(new_diagnostics.get(url, {
            "last_success_at": None,
            "last_failure_at": None,
            "consecutive_failures": 0,
            "total_checks": 0,
            "successful_checks": 0
        }))
        diag["total_checks"] = diag.get("total_checks", 0) + 1

        if res["is_online"]:
            diag["last_success_at"] = res["checked_at"]
            diag["consecutive_failures"] = 0
            diag["successful_checks"] = diag.get("successful_checks", 0) + 1
        else:
            diag["last_failure_at"] = res["checked_at"]
            diag["consecutive_failures"] = diag.get("consecutive_failures", 0) + 1

        recent_up_pct = round((sum(1 for h in hist if h["ok"]) / len(hist)) * 100, 1) if hist else (100.0 if res["is_online"] else 0.0)
        diag["recent_uptime_percent"] = recent_up_pct
        diag["sample_count"] = len(hist)
        new_diagnostics[url] = diag

        if prev_urls_state and url in prev_urls_state:
            old_online = prev_urls_state[url].get("is_online")
            if old_online != res["is_online"]:
                changed_urls.add(url)

    # 判斷每日報告條件
    trigger_daily = False
    if daily_report_enabled and not is_startup:
        if last_daily_report_date != today_str:
            if not daily_report_time or now_time_str >= daily_report_time:
                trigger_daily = True

    should_send = False
    report_type = "status_change"

    if force_send:
        should_send = True
        report_type = "forced"
        print("[條件觸發] 強制發送模式 (--force-send)", flush=True)
    elif is_startup:
        if send_on_startup:
            should_send = True
            report_type = "startup"
            print("[條件觸發] 系統初次啟動，發送初始狀態報告", flush=True)
            last_daily_report_date = today_str
        else:
            print("[資訊] 系統初次啟動但設定不發送初始報告，已記錄當前狀態", flush=True)
    elif len(changed_urls) > 0:
        should_send = True
        report_type = "status_change"
        print(f"[條件觸發] 偵測到 {len(changed_urls)} 個網址狀態變更！準備發送通知", flush=True)
    elif trigger_daily:
        should_send = True
        report_type = "daily"
        print(f"[條件觸發] 到達每日報告排程時間 ({daily_report_time})，準備發送例行報告", flush=True)
        last_daily_report_date = today_str
    else:
        print("[維持原狀] 所有網址狀態均無變更且未達每日排程，略過發送", flush=True)

    if should_send:
        embed = build_discord_embed(current_results, changed_urls, report_type=report_type)
        send_discord_webhook(webhook_url, embed, dry_run=dry_run)

    updated_state = {
        "last_daily_report_date": last_daily_report_date,
        "urls": new_urls_state,
        "history": new_history,
        "diagnostics": new_diagnostics
    }
    save_state(updated_state)
    export_status_json(current_results, state=updated_state)
    if auto_push:
        git_push_status()
    return updated_state

def main():
    parser = argparse.ArgumentParser(description="ALL.Net 音樂遊戲與 Aime 服務在線狀態監控器")
    parser.add_argument("--once", action="store_true", help="執行單次檢測後立即退出")
    parser.add_argument("--interval", type=int, help="自訂輪詢間隔秒數 (覆寫設定檔)")
    parser.add_argument("--dry-run", action="store_true", help="測試模式，不實際發送 Discord Webhook")
    parser.add_argument("--force-send", action="store_true", help="無論狀態是否改變皆強制發送 Webhook")
    parser.add_argument("--git-push", action="store_true", help="檢測完成後自動 git commit 並 push 最新狀態快照至遠端倉庫 (更新 GitHub Pages)")
    args = parser.parse_args()

    config = load_config()
    if args.interval:
        config["check_interval_seconds"] = args.interval

    interval = config["check_interval_seconds"]
    print("=" * 60, flush=True)
    print(" 🎮 ALL.Net & Aime 服務狀態監控器 (頂級排版升級版)", flush=True)
    print(f" 監控目標數量: {len(config['targets'])} 個", flush=True)
    print(f" 輪詢間隔: {interval} 秒", flush=True)
    print(f" 每日例行推播: {'已啟用 (' + config.get('daily_report_time', '09:00') + ')' if config.get('daily_report_enabled') else '停用'}", flush=True)
    print(f" 專屬 Logo 狀態: {'已載入 (' + LOGO_FILE + ')' if os.path.isfile(LOGO_FILE) else '未找到'}", flush=True)
    print(f" 自動 Git 推送: {'已啟用 (自動同步 GitHub Pages)' if args.git_push else '停用'}", flush=True)
    print(f" 乾跑測試 (Dry-Run): {'啟用' if args.dry_run else '關閉'}", flush=True)
    print(f" 單次執行模式: {'是' if args.once else '否 (常駐運行)'}", flush=True)
    print("=" * 60, flush=True)

    state = load_state()

    if args.once:
        run_check_cycle(config, state, dry_run=args.dry_run, force_send=args.force_send, auto_push=args.git_push)
        print("[完成] 單次檢測結束", flush=True)
        return

    # 常駐輪詢模式
    try:
        while True:
            state = run_check_cycle(config, state, dry_run=args.dry_run, force_send=args.force_send, auto_push=args.git_push)
            args.force_send = False
            print(f"\n[等待中] 倒數 {interval} 秒後進行下一次檢測... (按 Ctrl+C 結束)", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[中斷] 接收到退出訊號，已安全終止監控程式。", flush=True)

if __name__ == "__main__":
    main()
