# Issue 11：docker-bug

來源：https://github.com/s12ryt/docker-keep-alive/issues/11

## 原始錯誤

Docker log 中 Telegram polling 出現：

```text
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
```

## 問題理解

Telegram Bot API 的 long polling (`getUpdates`) 同一時間只能有一個 consumer。當同一個 `bot_id` 被另一個容器、舊程序、本機測試程式或其他部署同時使用時，新的 polling loop 會收到 `telegram.error.Conflict`。

目前 `run_bot()` 直接呼叫：

```python
await application.updater.start_polling(drop_pending_updates=True)
```

沒有提供 `error_callback`，因此 python-telegram-bot 會用預設 callback 把 Conflict 以完整 traceback 重複打到 Docker log。除此之外，`run_bot()` 只回傳 notify callable，lifespan shutdown 時也沒有顯式停止 Telegram updater/application，會增加重啟或測試環境中殘留 polling 的風險。

## 實作策略

- 新增 `BotRuntime` 包裝 Telegram `Application`：
  - `notify(text)`：維持原本保活通知能力。
  - `stop_polling()`：安全停止 updater polling。
  - `shutdown()`：服務關閉時依序停止 updater、application 並 shutdown application。
- `run_bot()` 改回傳 `BotRuntime`。
- `start_polling()` 增加 non-async `error_callback`：
  - 遇到 `telegram.error.Conflict` 時只記錄簡短 warning，不再輸出完整 traceback。
  - 安排背景 task 停止本 instance 的 polling，讓 Web 與 keepalive 服務繼續運作。
  - 其他 TelegramError 仍保留 exception log 方便排查。
- `main.py` lifespan 保存 `bot_runtime`，shutdown 時顯式 `await bot_runtime.shutdown()`。
- README 補充同一 bot token 只能跑一個 polling instance；若發生 Conflict，本 instance 會停用 Telegram polling 但 Web/keepalive 持續運作。
- 補測試：
  - Conflict callback 會安排停止 polling 且不拋例外。
  - `BotRuntime.shutdown()` 會呼叫 updater/application 停止流程。

## 驗收標準

- Docker log 不再因 Conflict 顯示重複 traceback。
- 發生 Conflict 時不讓整個 Web/keepalive 服務退出。
- 正常 shutdown 會停止 Telegram polling/application。
- 測試通過。
