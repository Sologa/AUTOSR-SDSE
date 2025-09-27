# 在 AUTOSR-SDSE 專案中使用 sdse-uv 環境

`sdse-uv` 目錄是透過 [uv](https://github.com/astral-sh/uv) 建立的 Python 專案，內含虛擬環境與依賴鎖定檔。以下整理如何在主專案中共用這個環境，並說明如何用 uv 安裝額外套件。

## 安裝／同步依賴

每次 `pyproject.toml` 或 `uv.lock` 更新後，請在專案根目錄執行：

```bash
uv sync --project sdse-uv
```

這會依照鎖定檔建立（或更新） `sdse-uv/.venv` 中的虛擬環境。

## 新增套件

若需要安裝新的套件，建議直接透過 uv 修改 `sdse-uv/pyproject.toml`，這樣會同時更新鎖定檔並確保團隊環境一致。

- 安裝一般依賴：

  ```bash
  uv add --project sdse-uv <套件名稱>
  ```

- 安裝開發用依賴：

  ```bash
  uv add --project sdse-uv --dev <套件名稱>
  ```

執行後，uv 會自動更新 `pyproject.toml`、`uv.lock`，並立即將新套件同步到 `sdse-uv/.venv`。如果只想暫時試用某個套件而不更新專案設定，可改用：

```bash
uv pip install --project sdse-uv <套件名稱>
```

此指令只會變更虛擬環境，不會修改設定檔。使用完畢若不需要保留，請執行 `uv sync --project sdse-uv` 將環境還原到鎖定檔狀態。


## Ruff 靜態檢查工具

本專案使用 [ruff](https://docs.astral.sh/ruff/) 作為 linter / formatter。請依下列步驟安裝與驗證：

```bash
uv add --project sdse-uv --dev ruff
source sdse-uv/.venv/bin/activate
ruff --version
```

安裝完成後，常見指令如下：

```bash
ruff check .        # 執行靜態檢查
ruff format .       # 依 ruff 規則自動格式化
```

若 ruff 報告問題，可搭配 `ruff check --fix` 嘗試自動修正，或依輸出提示手動調整程式碼。完成修正後請重新執行檢查以確保清晰。

## 更新既有套件

若要升級已經列在 `pyproject.toml` 中的依賴，有兩種常見情境：

- **更新單一套件到可用最新版本**：

  ```bash
  uv add --project sdse-uv --upgrade <套件名稱>
  ```

  若要限定升級到特定版本，也可以直接指定版本號：

  ```bash
  uv add --project sdse-uv <套件名稱>==<版本號>
  ```

- **重新解析並升級全部依賴**：

  ```bash
  uv sync --project sdse-uv --upgrade
  ```

每次升級後 `pyproject.toml` 與 `uv.lock` 都會被更新，請記得將這兩個檔案一併提交到版本控制。若升級造成環境異常，可再度執行 `uv sync --project sdse-uv` 回復到鎖定檔狀態。

## 啟用虛擬環境

若希望之後的命令都使用此環境，可以手動啟用：

```bash
source sdse-uv/.venv/bin/activate
```

啟用後，終端機提示會出現 `(sdse-uv)`，此時執行 `python`、`pip`、`pytest` 等命令都會使用該虛擬環境。

結束工作時可使用 `deactivate` 退出虛擬環境。

## 直接使用 uv 執行命令

若不想手動啟用虛擬環境，可利用 `uv run` 包住每個指令，uv 會自動在 `sdse-uv/.venv` 中執行：

```bash
uv run --project sdse-uv python unified_research_pipeline.py ...
uv run --project sdse-uv python -m unittest discover -s test
uv run --project sdse-uv pytest
```

依照需求替換成要執行的任意 Python 腳本或模組即可。這種方式適合在腳本、Makefile 甚至 CI 設定中直接指定使用 `sdse-uv` 的環境。

## 建議工作流程

1. 初次安裝或依賴變動後，執行 `uv sync --project sdse-uv`。
2. 互動式開發：`source sdse-uv/.venv/bin/activate`，完成後再 `deactivate`。
3. 自動化腳本或 CI：以 `uv run --project sdse-uv ...` 包住指令。

透過上述步驟，就能確保 AUTOSR-SDSE 主專案與 `sdse-uv` 目錄共用同一組 Python 套件與解釋器設定。MD
