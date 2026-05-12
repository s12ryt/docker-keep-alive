# Issue #21：bug 與可優化點紀錄

來源：<https://github.com/s12ryt/docker-keep-alive/issues/21>

## 問題整理

Issue #21 指出以下 bug 與維護性問題：

1. `keepalive_loop` 啟動後會立即 ping，頻繁重啟時可能造成非預期流量與通知。
2. Telegram `/del_url` 列表直接顯示原始 URL，和網頁遮罩行為不一致，可能洩漏 URL token。
3. `backup.py` 的 `_engine_cache` 是模組層級全域狀態，缺少測試清理入口。
4. `ping_once` 用 list index 回寫狀態，ping 期間若 URL 被刪除/插入，可能更新到錯誤 URL。
5. `configured_timezone()` 每次呼叫都重新讀取並解析 `TZ`。
6. `backup_loop` 備份失敗時完全吞掉 exception，無法診斷問題。
7. `/del_url` pending 只保存 index，使用者回覆前清單變動時可能刪錯項目。
8. Docker runtime 未複製 `pyproject.toml`，未來若加入 metadata/entry point 會缺檔。
9. `/s12ryt` endpoint 硬編碼，fork 使用不方便。
10. 啟動恢復備份是同步 DB 查詢，會阻塞 lifespan event loop。

## 修正策略

- `keepalive_loop` 增加初始延遲，預設先等待一個 interval 再 ping；測試可用 `initial_delay_seconds=0` 加速。
- 將 URL masking helper 放到 `state.py`，供網頁、Telegram `/state`、`/del_url` 共用。
- `/del_url` pending 保存當次 URL 清單，回覆編號後用 URL 字串刪除，避免 index 漂移刪錯。
- `ping_once` 改用 URL 字串回寫狀態，避免 index race condition。
- `_engine_cache` 加 lock，並提供 `clear_engine_cache()` 給測試清理。
- `configured_timezone()` 用 `functools.cache` 快取解析結果，測試可呼叫 `cache_clear()`。
- `backup_loop` 使用 logger.exception 記錄備份失敗，且同步 DB 寫入改用 `asyncio.to_thread()`。
- `restore_latest_backup` 改為 async，lifespan 透過 await 執行 thread 包裝的 DB 查詢。
- `KEEPALIVE_PATH` 支援自訂保活端點，預設仍保留 `/s12ryt` 向後相容。
- Dockerfile 複製 `pyproject.toml` 到 runtime。

## 驗證項目

- 補上 keepalive 初始延遲、URL race、del_url 遮罩/字串刪除、cache 清理、timezone cache、自訂 keepalive path 與 async restore 測試。
- 執行 `py -m pytest -q`。
