# Issue 16：TZ 變量

來源：https://github.com/s12ryt/docker-keep-alive/issues/16

## 原始需求

Issue 內容：

```text
使用+0800這種格式進行時區的轉換
```

## 現況

- `app/state.py` 的 `utc_now()` 固定使用 UTC，首頁 `started_at`、保活檢查時間 `last_checked_at` 都會顯示 `+00:00`。
- `app/backup.py` 的備份 `created_at` 也固定以 UTC 建立並在 `/rebackup` 列表中顯示。
- README 沒有說明可用 `TZ` 控制顯示時區。

## 目標

- 支援 `TZ` 環境變數使用 `+0800`、`-0530` 這類格式。
- 服務內部產生與顯示的時間要套用指定 offset。
- 若 `TZ` 缺失或格式不合法，維持 UTC，避免服務啟動失敗。
- 補上測試與 README 說明。

## 實作策略

- 新增 `app/timezone.py`：
  - `timezone_from_offset(value)`：解析 `+HHMM` / `-HHMM`。
  - `configured_timezone()`：讀取 `TZ`，不合法則回 UTC。
  - `now_iso()`：回傳指定時區的 ISO 時間。
  - `format_datetime()`：將資料庫 datetime 轉成指定時區顯示。
- `app/state.py` 保留既有 `utc_now()` 名稱以避免大範圍改動，但改為回傳 `now_iso()`。
- `app/backup.py` 備份建立與列表顯示套用 configured timezone。
- README 新增 `TZ` 環境變數說明。

## 驗收標準

- `TZ=+0800` 時，新產生的狀態時間包含 `+08:00`。
- `TZ=-0530` 時，新產生的狀態時間包含 `-05:30`。
- 不合法 `TZ` 不會讓服務失敗，會回到 UTC。
- 備份列表時間會用指定時區顯示。
- 測試通過。
