# docker-keep-alive

一個可用 Docker 部署的保活機器人：提供網頁流量入口、Telegram Bot 控制面板、定期訪問目標網址，以及可選的 MySQL/PostgreSQL 備份。

## 功能

- 網頁首頁 `/`：查看 bot 與保活網址狀態。
- 保活入口 `/s12ryt`：供第三方保活服務訪問。
- Telegram Bot：新增/刪除網址、查看狀態、開關通知、備份/恢復。
- Docker 映像：可由 GitHub Actions 自動推送至 GHCR。
- 自動測試：Pull Request 與 push 時執行 pytest。

## 環境變數

| 變數 | 必填 | 說明 |
| --- | --- | --- |
| `bot_id` | 是 | Telegram Bot Token |
| `chat_id` | 是 | 允許使用的 Telegram chat id（單使用者） |
| `backup` | 否 | MySQL/PostgreSQL 連線網址，用於每 10 分鐘備份 |
| `PORT` | 否 | Web 服務連接埠，預設 `8080` |
| `KEEPALIVE_INTERVAL_SECONDS` | 否 | 保活間隔，預設 `300` |
| `BACKUP_INTERVAL_SECONDS` | 否 | 備份間隔，預設 `600` |
| `TELEGRAM_CONFLICT_RETRY_SECONDS` | 否 | Telegram polling 衝突後重試間隔，預設 `60` |

也支援大寫別名：`BOT_ID`、`CHAT_ID`、`BACKUP`。

設定 `backup` 後，服務啟動或重啟時會自動讀取資料庫內最新備份並恢復狀態；定期備份每次完成後只保留最新備份，以避免資料庫長期累積過多資料。

## Telegram 指令

- `/start`：授權使用者回覆 `ciallo~` 並顯示指令列表。
- `/help`：顯示指令列表。
- `/commands`：顯示指令列表。
- `/state`：回覆目前保活網址與狀態。
- `/sub-url` 或 `/sub_url`：新增保活網址。
- `/del-url` 或 `/del_url`：列出網址編號並刪除指定項目。
- `/notify`：切換每次保活後的通知。
- `/backup`：建立備份；未設定 `backup` 時會要求輸入資料庫網址。
- `/rebackup`：列出備份並恢復指定備份；未設定 `backup` 時會要求輸入資料庫網址。

未授權 chat id 會直接忽略，不回覆訊息以節省流量。
未知指令會提示使用 `/help` 查看可用指令。
啟動時會透過 Telegram Bot API `setMyCommands` 註冊原生命令選單；因 Telegram 原生選單不允許指令名稱包含 `-`，選單中使用 `/sub_url`、`/del_url`，原本 issue 要求的 `/sub-url`、`/del-url` 仍然可用。
同一個 Telegram Bot Token 同一時間只能有一個 long polling instance；如果另一個容器或程序正在使用同一個 token，本服務會暫停本 instance 的 Telegram polling、避免重複 traceback，Web 與保活功能仍會繼續運作，並依 `TELEGRAM_CONFLICT_RETRY_SECONDS` 自動重試恢復 polling。

## 本機執行

```bash
python -m venv .venv
pip install -r requirements-dev.txt
bot_id=123:abc chat_id=123456 python -m app.main
```

## Docker

```bash
docker build -t docker-keep-alive .
docker run -p 8080:8080 -e bot_id=123:abc -e chat_id=123456 docker-keep-alive
```
