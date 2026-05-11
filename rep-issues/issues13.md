# Issue 13：tgbot polling conflict 後無法自動恢復

來源：https://github.com/s12ryt/docker-keep-alive/issues/13

## 原始問題

Issue 內容只有一段目前服務輸出的訊息：

```text
Telegram polling conflict detected; another bot instance is already using getUpdates. Stopping polling for this instance while keeping the web service alive.
```

這代表 Issue #11 的衝突處理已避免刷完整 traceback，但新的體驗問題是：

- 使用者只看到 Telegram polling 被停止，會以為 tgbot 壞掉。
- 如果衝突來源只是舊容器或部署期間短暫殘留，當舊 instance 結束後，本服務不會自動恢復 polling。
- 訊息沒有提供重試資訊，也沒有設定項能調整重試間隔。

## 目標

- 保留 Issue #11 的行為：遇到 `telegram.error.Conflict` 不要重複輸出完整 traceback，Web 與保活功能仍繼續運作。
- 新增 Telegram polling conflict 自動恢復：停止本次 polling 後等待一段時間再重新啟動 polling。
- 避免同一個 conflict 連續排程多個重試 task。
- 增加可調整的環境變數，讓使用者可依部署平台調整重試間隔。
- README 說明 conflict 後會自動重試。

## 實作策略

- `Settings` 新增 `telegram_conflict_retry_seconds`，讀取 `TELEGRAM_CONFLICT_RETRY_SECONDS`，預設 `60`。
- `BotRuntime` 新增：
  - `conflict_retry_seconds`
  - `start_polling()` 統一啟動 polling 並掛上 error callback。
  - `schedule_conflict_recovery()`：若尚未有重試 task，建立背景 task。
  - `_recover_polling_after_conflict()`：停止 polling、等待 backoff、若 application 仍 running 則重新 start polling。
  - shutdown 時取消 conflict retry task。
- `polling_error_callback()` 遇到 `Conflict` 時改成排程 recovery，而不是永久停止 polling。
- `run_bot()` 接收 conflict retry 秒數並使用 `runtime.start_polling()`。
- 補測試：
  - conflict callback 只排程一次 recovery。
  - shutdown 會取消 pending conflict retry task。

## 驗收標準

- Conflict 時不刷完整 traceback。
- Conflict 時會停止目前 polling 並排程自動重試。
- 重試 task 不會重複排程。
- shutdown 會取消重試 task，避免背景 task 殘留。
- README 有環境變數與行為說明。
- 測試通過。
