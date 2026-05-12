# memory

- 遠端倉庫 `s12ryt/docker-keep-alive` 目前為空倉庫。
- issue #1 要求：網頁、`/s12ryt` 端點、Telegram Bot 控制、Docker 映像、GHCR workflow、測試 workflow、可選 MySQL/PostgreSQL 備份。
- 環境變數沿用需求命名：`bot_id`、`chat_id`、`backup`，同時支援大寫別名方便部署。
- Issue #19 後，公開 `/api/state` 改用 `public_snapshot()`，不得回傳 `backup_url`；Telegram `/state` 與網頁顯示網址需使用遮罩。
