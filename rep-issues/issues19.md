# Issue #19：Bug 與可優化點分析紀錄

來源：<https://github.com/s12ryt/docker-keep-alive/issues/19>

## Issue 摘要

Issue #19 彙整目前專案的安全性、功能正確性與維護性問題。最高優先級包含：

1. `/api/state` 會公開 `backup_url`，其中可能包含資料庫帳密。
2. `/rebackup` 使用手動輸入 DB URL 列出備份後，恢復時卻改用 `state.get_backup_url()`，導致找不到手動 URL 裡的備份。
3. 同步 SQLAlchemy 操作在 async Telegram/背景任務中直接執行，可能阻塞 event loop。
4. `TZ=Asia/Taipei` 這類常見 IANA 時區格式不支援，且目前靜默 fallback UTC。
5. 其他低風險改善：Docker non-root、pending action TTL、Telegram `/state` URL masking、設定值解析錯誤訊息。

## 採取策略

此 issue 是一份多點分析，不適合一次大規模改寫整個服務。優先處理高風險與可用小步驟可靠修正的項目：

- 安全性：移除公開 API 內的 `backup_url`；Telegram `/state` 使用遮罩網址。
- 功能性：restore pending 狀態保存當次使用的 `database_url`。
- 穩定性：為 backup engine cache 加 lock；同步 DB 操作用 `asyncio.to_thread()` 包裝，避免在 async handler/loop 阻塞 event loop。
- 時區：支援 IANA zoneinfo，保留既有 `+HHMM` / `-HHMM` offset 行為。
- 設定：對整數環境變數提供清楚錯誤訊息。
- 容器：改為 non-root user 執行。
- pending：新增 TTL 清理，避免長時間殘留狀態。

## 待驗證

- 新增/更新測試覆蓋上述修正。
- 執行 `py -m pytest -q`。
- 建立分支並提交 PR 到 `s12ryt/docker-keep-alive`。
