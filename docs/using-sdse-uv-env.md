# 在 AUTOSR-SDSE 專案中使用 sdse-uv 環境

`sdse-uv` 目錄是透過 [uv](https://github.com/astral-sh/uv) 建立的 Python 專案，內含虛擬環境與依賴鎖定檔。以下整理如何在主專案中共用這個環境。

## 安裝／同步依賴

每次 `pyproject.toml` 或 `uv.lock` 更新後，請在專案根目錄執行：

```bash
uv sync --project sdse-uv
```

這會依照鎖定檔建立（或更新） `sdse-uv/.venv` 中的虛擬環境。

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
