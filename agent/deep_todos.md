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
- [x] Issue #8 數據庫優化：定期備份只保留最新一筆，啟動/重啟時自動從資料庫載入最新備份，並補上 SQLite 測試。
- [x] Issue #7 bug/潛在問題修補：補齊 state 鎖保護 API、保活並發、BackupStore engine 重用、避免手動 DB URL 覆蓋自動備份 URL、移除 lifespan 全域 task list、放寬依賴版本、改用 multi-stage Docker build，並補文件與測試。
- [x] Issue #11 docker-bug：處理 Telegram getUpdates Conflict，改為簡短 warning 並停止本 instance polling，同時補上 Telegram runtime shutdown，避免容器 log 重複 traceback。
- [x] Issue #13 tgbot：Telegram polling conflict 後改為依 `TELEGRAM_CONFLICT_RETRY_SECONDS` 自動重試恢復 polling，並避免重複排程 retry task。
- [x] Issue #15 網頁隱私部分：首頁遮罩保活網址並移除第三方保活端點顯示，同時保留 `/s12ryt` endpoint 功能。
- [x] Issue #16 TZ 變量：支援 `TZ=+0800` / `TZ=-0530` 這類 offset 格式，狀態時間與備份列表會依指定時區顯示。
- [x] Issue #19 分析修補：隱藏公開 API 的 backup URL、修正手動 DB restore 來源、同步 DB 操作用 thread 包裝、支援 IANA TZ、pending TTL、Docker non-root 與設定錯誤提示。
- [x] Issue #21 bug 與可優化點：延遲初始保活、修正 URL index race、遮罩 Telegram 刪除清單、備份 engine cache 可清理、記錄備份例外、非阻塞啟動恢復、自訂保活路徑並更新 Docker/README。
