# Issue 8：數據庫優化

來源：https://github.com/s12ryt/docker-keep-alive/issues/8

## 原始需求

- `定期刪除`：每 10 分鐘清除其餘備份。
- `啟動/重啟自動加載最新備份`：服務啟動或重啟時，全自動讀取數據庫並載入最新備份。

## 目前程式現況

- `app/backup.py`
  - `BackupStore.create_backup(payload)` 只會新增備份。
  - `BackupStore.list_backups()` 以 `created_at desc` 列出備份。
  - `BackupStore.get_backup(id)` 可讀取指定備份。
  - 尚無「取得最新備份」或「刪除舊備份」功能。
- `app/keepalive.py`
  - `backup_loop()` 每 `BACKUP_INTERVAL_SECONDS` 秒建立一筆備份。
  - 預設間隔為 600 秒，即 10 分鐘。
  - 尚未清理舊備份，因此長期執行會持續累積資料。
- `app/main.py`
  - 啟動時只用 env `backup` 設定 `state.backup_url`。
  - 尚未在啟動時自動從資料庫恢復最新備份。

## 實作計畫

1. 在 `BackupStore` 增加：
   - `get_latest_backup()`：讀取最新一筆備份 payload。
   - `delete_backups_except(keep_id)`：刪除指定 id 以外的備份。
   - `create_backup(..., keep_only_latest=True)`：建立備份後保留最新備份並刪除其餘備份。
2. 更新定期備份流程：
   - 每 10 分鐘建立新備份後，清除其餘舊備份。
3. 更新啟動流程：
   - 若 env `backup` 存在，啟動時先連線資料庫。
   - 若有最新備份，呼叫 `state.restore(latest_payload)` 自動載入。
   - 載入失敗不應讓 web 服務整體崩潰，避免資料庫短暫異常造成服務無法啟動。
4. 補測試：
   - SQLite roundtrip 測試應驗證只保留最新備份。
   - 測試可讀取最新備份。

## 驗收標準

- 定期備份後資料庫只保留最新一筆備份。
- 服務啟動時，若 `backup` 指向的資料庫已有備份，會自動恢復最新狀態。
- 既有 `/backup`、`/rebackup` 手動功能仍可使用。
- 測試通過。
