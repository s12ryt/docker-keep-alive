# Issue 15：網頁隱私部分

來源：https://github.com/s12ryt/docker-keep-alive/issues/15

## 原始需求

Issue 內容：

```text
網址不要全部顯示要碼掉
"第三方保活端點"不要顯示
```

## 現況

- `app/main.py` 的首頁 `/` 會直接輸出每個保活網址完整值：`{item['url']}`。
- 首頁上方會顯示：`第三方保活端點：<code>/s12ryt</code>`。
- 這會讓公開或半公開的狀態頁暴露：
  - 完整保活目標網址。
  - 固定的第三方保活路徑 `/s12ryt`。

## 目標

- 首頁 `/` 只顯示遮罩後的網址，不直接暴露完整 URL。
- 首頁不再顯示「第三方保活端點」文字與 `/s12ryt`。
- `/s12ryt` endpoint 本身仍保留，避免破壞第三方保活服務。
- `/api/state` 維持原始資料，供程式化狀態查詢與內部用途使用。
- 補上測試，避免後續回歸。

## 實作策略

- 在 `app/main.py` 新增 `mask_url_for_display(url)`：
  - 保留 scheme 與 hostname 的首尾少量字元。
  - path/query/fragment 全部以遮罩表示。
  - URL 格式異常時仍用通用遮罩處理。
- 首頁表格使用遮罩後的 URL，並用 `html.escape` 避免 HTML 注入。
- 首頁描述移除「第三方保活端點：/s12ryt」。
- `tests/test_web.py` 新增：
  - 首頁不顯示完整 URL、query token、path secret。
  - 首頁不顯示「第三方保活端點」與 `/s12ryt`。
  - URL 遮罩 helper 仍保留可辨識的 scheme/部分 hostname。

## 驗收標準

- 首頁 `/` 看不到完整保活網址。
- 首頁 `/` 看不到「第三方保活端點」與 `/s12ryt`。
- `/s12ryt` endpoint 繼續正常回應。
- 測試通過。
