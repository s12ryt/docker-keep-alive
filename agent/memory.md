# memory

- 遠端倉庫 `s12ryt/docker-keep-alive` 目前為空倉庫。
- issue #1 要求：網頁、`/s12ryt` 端點、Telegram Bot 控制、Docker 映像、GHCR workflow、測試 workflow、可選 MySQL/PostgreSQL 備份。
- 環境變數沿用需求命名：`bot_id`、`chat_id`、`backup`，同時支援大寫別名方便部署。
- Issue #19 後，公開 `/api/state` 改用 `public_snapshot()`，不得回傳 `backup_url`；Telegram `/state` 與網頁顯示網址需使用遮罩。
- Issue #21 後：`KEEPALIVE_PATH` 可自訂保活入口（預設 `/s12ryt`）；保活迴圈預設啟動後先等待 interval，避免立即 ping；Telegram 顯示網址需遮罩，刪除操作以 pending URL 字串而非目前 index 為準。
- Issue #24 後：備份必須使用 `AppState.backup_snapshot()`，不得把 `backup_url` 寫入 DB payload；`restore()` 不能用舊 payload 覆蓋目前環境/狀態中的 DB URL，除非目前沒有設定；Telegram restore 缺少 DB URL 時需回覆「沒有設定資料庫。」。
