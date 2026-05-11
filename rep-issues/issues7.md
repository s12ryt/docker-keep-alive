# Issue 7：Bug / 潛在問題

來源：https://github.com/s12ryt/docker-keep-alive/issues/7

## 原始問題整理

Issue 指出目前程式有以下 bug 或可維護性問題：

1. `keepalive.py` 直接改 `TargetUrl` 欄位，繞過 `AppState` 的 `RLock`，有 race condition。
2. `telegram_bot.py` 直接裸寫 `notify_enabled`，read-modify-write 沒有鎖。
3. `telegram_bot.py` 手動備份/恢復流程會直接覆蓋 `state.backup_url`，可能讓一次性輸入的 DB URL 影響自動備份 loop。
4. `BackupStore` 每次初始化都建立新 SQLAlchemy engine，連線池未重用，可能造成效率差或連線累積。
5. `main.py` 使用全域 `background_tasks`，反覆 lifespan 啟停時有全域狀態風險。
6. `requirements.txt` 版本 pin 太嚴，安全更新彈性不足。
7. `Dockerfile` 未使用 multi-stage build，映像偏大。
8. `keepalive.py` 保活逐一 await，遇到慢網址會卡住整輪。
9. README 缺 `BACKUP_INTERVAL_SECONDS` 文件。
10. 備份列表無限制。此項已在 Issue #8 中改成定期備份只保留最新一筆，但手動恢復列表仍應保留合理 limit。

## 實作策略

本次優先修補高風險與中低成本項目，避免大幅改變產品行為：

- 在 `AppState` 補齊鎖保護 API：
  - `list_urls()`：保活流程取得 URL 快照，不直接迭代共享 list。
  - `update_url_status()`：一次性鎖內更新保活狀態。
  - `toggle_notify()`：鎖內切換通知。
  - `get_backup_url()` / `set_backup_url()`：集中管理 backup URL。
- `keepalive.py`：
  - 以 `asyncio.gather` 並發 ping 多個 URL。
  - 以 `update_url_status()` 寫回狀態，避免直接修改共享物件。
  - `backup_loop()` 透過 `get_backup_url()` 讀取，避免裸讀。
- `telegram_bot.py`：
  - `/notify` 改用 `toggle_notify()`。
  - `/backup`、`/rebackup` 在使用者手動輸入 DB URL 時不再覆蓋自動備份用的 env `backup`，避免副作用。
  - 只有原本已存在 `state.backup_url` 時，才沿用該自動備份 URL。
- `BackupStore`：
  - 增加 engine cache，讓相同 database URL 重用 engine。
  - `list_backups(limit=20)` 增加預設數量限制。
- `main.py`：
  - lifespan 內使用 local `tasks`，移除跨 lifespan 全域 `background_tasks`。
- `requirements.txt`：
  - 將主要 runtime dependency 改成 `>=` 搭配相容上限，保留取得安全修復的彈性。
- `Dockerfile`：
  - 改為 multi-stage build，builder 先產生 wheels，runtime 只安裝 wheelhouse 內容並複製 app。
- 文件與測試：
  - README 補上 `BACKUP_INTERVAL_SECONDS`。
  - 新增/更新測試覆蓋鎖保護 API、並發保活、手動 DB URL 不覆蓋自動備份 URL、engine 重用與列表 limit。

## 驗收標準

- keepalive 狀態更新不再裸寫共享 `TargetUrl`。
- 通知切換不再裸寫 `notify_enabled`。
- 一次性手動備份/恢復 URL 不會覆蓋現有自動備份 URL。
- 同一個 DB URL 的 `BackupStore` 重用 engine。
- 背景任務不再依賴全域 task list。
- 多 URL 保活可並發執行。
- README 有 `BACKUP_INTERVAL_SECONDS` 說明。
- requirements 不再完全鎖死 patch 版本。
- Dockerfile 使用 multi-stage build。
- 測試通過。
