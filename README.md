# ALL.Net 服務在線狀態監控系統 (ALL.Net Status Monitor)

針對 ALL.Net 旗下街機音樂遊戲（maimai DX、CHUNITHM、O.N.G.E.K.I.）個人數據服務 (NET)、官方網站與 Aime 認證平台開發的輕量化狀態監控工具。提供 Discord Webhook 結構化狀態推播與 GitHub Pages 靜態狀態儀表板。

---

## 系統架構

* **監控核心 (`monitor.py`)**：純 Python 3 標準函式庫實作，零外部相依。負責定時 HTTP/HTTPS 巡檢、狀態清洗、本機快取與資料序列化。
* **Discord 通知**：透過 Webhook multipart/form-data 封裝本地專屬 Logo，發送具備可用率進度條、業務分組與異動醒目的 Rich Embed。
* **靜態儀表板 (`index.html`)**：零前端框架，基於現代 CSS Tokens 與無障礙標準構建。支援深色/淺色模式切換、多語言（繁體中文 / 英文 / 日文）與非同步輪詢。
* **雲端自動化 (`.github/workflows/monitor.yml`)**：GitHub Actions 每 10 分鐘自動巡檢、更新 `status.json` 並推播至 GitHub Pages。

---

## 監控端點清單 (11 個目標)

| 類別 | 服務名稱 | 目標網址 | 判定標準 |
| :--- | :--- | :--- | :--- |
| **玩家數據服務 (NET)** | maimai DX (國際版 NET) | `https://maimaidx-eng.com/` | HTTP 200~399 |
| **玩家數據服務 (NET)** | maimai DX (日本版 NET) | `https://maimaidx.jp/` | HTTP 200~399 |
| **玩家數據服務 (NET)** | CHUNITHM-NET (日本版) | `https://new.chunithm-net.com/` | HTTP 200~399 |
| **玩家數據服務 (NET)** | CHUNITHM-NET (國際版) | `https://chunithm-net-eng.com/` | HTTP 200~399 |
| **玩家數據服務 (NET)** | O.N.G.E.K.I. (音擊 NET) | `https://ongeki-net.com/` | HTTP 200~399 |
| **帳號認證平台** | Aime 服務平台 (my-aime) | `https://my-aime.net/` | **僅限 HTTP 200** (其餘 403/451 視為離線) |
| **官方入口網站** | maimai (日本官方網站) | `https://maimai.sega.jp/` | HTTP 200~399 |
| **官方入口網站** | maimai (國際官方網站) | `https://maimai.sega.com/` | HTTP 200~399 |
| **官方入口網站** | CHUNITHM (國際官方網站) | `https://chunithm.sega.com/` | HTTP 200~399 |
| **官方入口網站** | CHUNITHM (日本官方網站) | `https://chunithm.sega.jp/` | HTTP 200~399 |
| **官方入口網站** | O.N.G.E.K.I. (日本官方網站) | `https://ongeki.sega.jp/` | HTTP 200~399 |

---

## 快速開始

### 環境需求

* Python 3.8+ (無須額外 `pip install`)

### 1. 設定 Webhook

複製設定檔範本並填入 Discord Webhook 網址：

```powershell
# Windows PowerShell
Copy-Item config.example.json config.json
```

編輯 `config.json`：

```json
{
  "discord_webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL",
  "check_interval_seconds": 60,
  "timeout_seconds": 10,
  "send_on_startup": true,
  "daily_report_enabled": true,
  "daily_report_time": "09:00"
}
```

> **安全提示**：`config.json` 與 `.env` 已列入 `.gitignore`，請勿將包含真實 Webhook 網址的設定檔提交至公開版本庫。亦可透過環境變數 `DISCORD_WEBHOOK_URL` 注入。

### 2. 啟動監控

```powershell
# 單次檢測並更新 status.json
python monitor.py --once

# 常駐監控 (依設定檔間隔持續輪詢)
python monitor.py

# 巡檢完成後自動提交並推送到 Git (適用於 GitHub Actions 或本機自動化)
python monitor.py --once --git-push
```

### 3. 執行測試

```powershell
python -m unittest discover tests
```

---

## Discord 推播機制

系統透過三種規則控制訊息發送，避免常態重複訊息洗版：

1. **初次啟動報告 (`send_on_startup`)**：程式啟動時發送一次全局健康度快照，確認監控進程運作正常。
2. **狀態變動警報 (State Delta)**：僅當任一目標站點的「在線 / 離線」狀態改變時發送。訊息頂部會標記狀態更迭項目（例如 `🔴 ➔ 🟢`），並附帶完整 11 站列表。
3. **每日定時總結 (`daily_report_enabled`)**：於每日指定時間（預設 `09:00`）發送一次例行回報。

---

## 設定檔參數說明

| 欄位名稱 | 型態 | 預設值 | 說明 |
| :--- | :--- | :--- | :--- |
| `discord_webhook_url` | string | `""` | Discord Webhook 完整 URL |
| `check_interval_seconds` | int | `60` | 常駐輪詢間隔秒數 |
| `timeout_seconds` | int | `10` | HTTP 請求超時上限 |
| `proxy` | string / null | `null` | HTTP/HTTPS 代理伺服器位置 |
| `send_on_startup` | bool | `true` | 是否於程式啟動時發送初始狀態報告 |
| `daily_report_enabled` | bool | `true` | 是否啟用每日定時總結報告 |
| `daily_report_time` | string | `"09:00"` | 每日總結觸發時間 (HH:MM 格式) |
| `targets` | array | (11 站) | 監控目標站點列表 (名稱、網址、分類、`strict_200`) |

---

## GitHub Pages 部署

1. 將本專案推送至 GitHub Repository。
2. 進入 Repository 的 **Settings** > **Secrets and variables** > **Actions**，新增 Repository Secret：
   * 名稱：`DISCORD_WEBHOOK_URL`
   * 數值：你的 Discord Webhook URL
3. 進入 **Settings** > **Pages**，將 Build and deployment 來源設為 **Deploy from a branch**（分支選取 `master` 或 `main`，目錄為 `/ (root)`）。
4. 內建之 `.github/workflows/monitor.yml` 會每 10 分鐘自動執行巡檢、更新 `status.json` 並推播至 GitHub Pages。

---

## 專案結構

```
.
├── .github/workflows/
│   └── monitor.yml           # GitHub Actions 定時巡檢工作流
├── assets/
│   └── logo.png              # 專案識別圖示 (用於 Webhook Embed 附件與網頁圖示)
├── tests/
│   ├── __init__.py
│   └── test_monitor.py       # 單元測試 (strict_200、狀態判定、清洗邏輯)
├── .env.example              # 環境變數設定範本
├── .gitignore                # Git 忽略清單 (排除 config.json, .env, state.json)
├── config.example.json       # 監控設定範本
├── index.html                # 狀態監控儀表板 (支援 Dark Mode & i18n)
├── monitor.py                # 監控核心程式 (檢測、快取、推播、git-push)
├── README.md                 # 專案說明文件
├── status.json               # 最新檢測快照 (供前端 index.html 讀取)
├── style.css                 # 儀表板版面樣式
└── tokens.css                # Design Tokens (現代極簡 Cobalt Light / Dark 配色)
```

---

## 授權

MIT License.
