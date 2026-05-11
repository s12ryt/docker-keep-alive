# deep_todos

- [x] 讀取 GitHub issue #1 需求。
- [x] 建立可部署的 Docker keep-alive 服務：網頁、`/s12ryt`、Telegram Bot、網址保活、備份/恢復。
- [x] 加入 Dockerfile 與 GitHub Actions：測試、自動建置 GHCR 映像。
- [x] 本機測試通過：`py -m pytest -q`（7 passed）。
- [x] 修正 GitHub Actions pytest 找不到 `app` package：新增 `pyproject.toml` 設定 `pythonpath = ["."]`。
- [x] 推送分支並建立 PR 到 `s12ryt/docker-keep-alive`。
- [x] 修正容器啟動失敗：Telegram `CommandHandler` 不接受 `/sub-url`、`/del-url` 的 hyphen 指令，改用 regex `MessageHandler`，並將 FastAPI startup/shutdown 改為 lifespan 消除 `on_event` 棄用警告。本機測試通過：`py -m pytest -q`（8 passed）。
- [x] 優化 Telegram 使用體驗：新增 `/help`、`/commands` 指令列表，`/start` 顯示指令列表，未知指令提示使用 `/help`，並補上測試與 README。
- [x] 新增 Telegram `setMyCommands` 原生命令選單：保留 `/sub-url`、`/del-url`，並提供可被 Telegram 選單註冊的 `/sub_url`、`/del_url` 別名。
