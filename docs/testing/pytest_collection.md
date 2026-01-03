# Pytest Collection Scope

## 目的
- 限定 pytest 只收集本專案測試，避免誤跑 `resources/` 內的外部套件測試。
- 讓 CI/本地測試在無額外依賴（例如 selenium）時仍可正常執行。

## 介面 / 參數
- 設定檔：`pytest.ini`
  - `testpaths`: 僅收集 `test/` 與 `tests/` 目錄。
  - `addopts`: 預設顯示簡要測試摘要。

## 使用範例
```bash
source sdse-uv/.venv/bin/activate
pytest -q
```

## 測試要點
- 確認 pytest 收集範圍僅包含 `test/` 或 `tests/`。
- `resources/` 下的第三方測試不應被收集。

## 已知限制
- 若未來新增測試目錄，需同步更新 `pytest.ini` 的 `testpaths`。
