# Issue #24 修復紀錄

來源：https://github.com/s12ryt/docker-keep-alive/issues/24

## Issue 摘要

Issue 指出目前備份、恢復與 pending action 有幾個安全性與穩定性問題：

1. **嚴重：備份 payload 會保存 `backup_url`**
   - `backup_url` 可能是含帳號密碼的 DB 連線字串，例如 `postgres://user:pass@host/db`。
   - `state.snapshot()` 會包含 `backup_url`。
   - `create_backup()` 呼叫端若直接序列化完整 snapshot，會把 DB 密碼明文存進備份表。
   - 備份 payload 也可能包含上一個 DB URL，造成遞迴洩漏。
   - 方向：備份用的 payload 不應包含 `backup_url`，應改用不含敏感欄位的 snapshot。

2. **恢復流程缺少資料庫 URL 時錯誤不清楚**
   - `_handle_restore()` 中 `database_url or self.state.get_backup_url()` 若兩者皆為 `None`，不應進入 `BackupStore(None)` 或回覆模糊的「找不到備份」。
   - 方向：明確檢查沒有資料庫 URL 時直接回覆「沒有設定資料庫」。

3. **`AppState.restore()` 不應讓備份 payload 覆蓋目前環境設定的 DB URL**
   - 目前邏輯會使用 payload 的 `backup_url`。
   - 環境變數或目前 state 的 DB URL 應優先。
   - 方向：只有目前 `backup_url` 為 `None` 時，才可從舊備份 payload 補入 `backup_url`（兼容舊資料）。

4. **pending action 過期 key 不會主動清理**
   - `BotController.pending` 目前只在讀取單一 key 時判斷 TTL。
   - 長期來看可能累積過期項目。
   - 方向：在設定與讀取 pending 前後清理過期 key。

5. **`configured_timezone()` 使用 cache，測試需避免跨測試污染**
   - 現有測試多處已手動 `cache_clear()`。
   - 方向：補上 pytest fixture 自動清理 cache，避免新增測試漏掉。

## 實作計畫

- 新增 `AppState.backup_snapshot()`，專供備份使用，永遠排除 `backup_url`。
- 將 Telegram 手動備份與定期備份改用 `backup_snapshot()`。
- 調整 `AppState.restore()`：保留目前 `backup_url` 優先，只有目前沒有設定時才讀取舊 payload 的 `backup_url`。
- 調整 `_handle_restore()`：沒有可用資料庫 URL 時明確回覆「沒有設定資料庫。」並停止。
- 調整 `BotController` pending 管理：新增過期清理方法，避免過期 key 長期留存。
- 在 `tests/conftest.py` 增加 autouse fixture 清理 `configured_timezone` cache。
- 補測試：備份 payload 不含 `backup_url`、restore 不覆蓋現有 DB URL、restore 缺 DB URL 回覆清楚錯誤、pending 過期清理。

## 驗收標準

- 本機 `py -m pytest -q` 全部通過。
- 備份內容不再包含 `backup_url`。
- 既有舊備份仍可恢復 URL 與通知狀態。
- 目前環境或 state 中設定的 DB URL 不會被舊備份覆蓋。
- Telegram 恢復流程在缺少 DB URL 時提供清楚訊息。
- pending action 過期後會被清掉。
