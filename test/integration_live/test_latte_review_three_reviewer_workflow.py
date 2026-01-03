from __future__ import annotations

import asyncio
import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Optional

import pandas as pd

try:  # pragma: no cover - 測試環境若缺 litellm 則建立最小 stub
    import litellm  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - 動態補上避免匯入失敗
    stub = types.ModuleType("litellm")
    stub.drop_params = True
    stub.enable_json_schema_validation = False

    def _raise_stub(*_: object, **__: object) -> None:
        raise RuntimeError("litellm stub 被呼叫，請改用 OpenAIProvider 或安裝 litellm。")

    stub.acompletion = _raise_stub  # type: ignore[attr-defined]
    stub.completion_cost = _raise_stub  # type: ignore[attr-defined]
    sys.modules["litellm"] = stub

try:  # pragma: no cover - 測試環境若缺 tokencost 則建立最小 stub
    from tokencost import calculate_prompt_cost, calculate_completion_cost  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - 動態補上避免匯入失敗
    tokencost_stub = types.ModuleType("tokencost")

    def _zero_cost(*_: object, **__: object) -> float:
        return 0.0

    tokencost_stub.calculate_prompt_cost = _zero_cost  # type: ignore[attr-defined]
    tokencost_stub.calculate_completion_cost = _zero_cost  # type: ignore[attr-defined]
    sys.modules["tokencost"] = tokencost_stub

try:  # pragma: no cover - 測試環境若缺 ollama 套件則建立防呆 stub
    import ollama  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - 動態補上避免匯入失敗
    ollama_stub = types.ModuleType("ollama")

    class _AsyncClient:  # type: ignore[misc]
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("ollama stub 被呼叫，請安裝 ollama 套件或避免使用 OllamaProvider。")

    ollama_stub.AsyncClient = _AsyncClient  # type: ignore[attr-defined]
    sys.modules["ollama"] = ollama_stub

try:  # pragma: no cover - 測試環境若缺 google genai 套件則建立防呆 stub
    import google  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - 動態補上避免匯入失敗
    google_stub = types.ModuleType("google")
    google_stub.__path__ = []  # type: ignore[attr-defined]

    genai_stub = types.ModuleType("google.genai")

    class _GenAIStub:  # type: ignore[misc]
        def __getattr__(self, name: str) -> object:
            raise RuntimeError("google.genai stub 被呼叫，請安裝 google-genai 套件或避免使用相關 provider。")

    class _GenAIClient:  # type: ignore[misc]
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("google.genai.Client stub 被呼叫，請安裝 google-genai 套件或避免使用相關 provider。")

    genai_stub.types = _GenAIStub()  # type: ignore[attr-defined]
    genai_stub.Client = _GenAIClient  # type: ignore[attr-defined]

    sys.modules["google"] = google_stub
    sys.modules["google.genai"] = genai_stub

from resources.LatteReview.lattereview.agents import TitleAbstractReviewer
from resources.LatteReview.lattereview.providers.openai_provider import OpenAIProvider
from resources.LatteReview.lattereview.workflows import ReviewWorkflow

from src.utils.env import load_env_file


METADATA_PATH = Path(
    # "test_artifacts/metadata_harvest/speech_language_models_per_query/arxiv_per_query_metadata.json"
    "test_artifacts/metadata_harvest/speech_language_models/arxiv_metadata_peer_reviewed.json"
)
OUTPUT_DIR = METADATA_PATH.parent

REASONING_EFFORT = "medium"


def _require_openai_key() -> None:
    load_env_file()
    assert os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY 未設定，無法執行 LatteReview 三人協作測試。"


def _resolve_top_k() -> Optional[int]:
    load_env_file()
    raw_value = os.environ.get("LATTE_REVIEW_TOP_K", "").strip()
    if not raw_value:
        return None
    try:
        top_k = int(raw_value)
    except ValueError as exc:  # pragma: no cover - 防呆驗證
        raise AssertionError("LATTE_REVIEW_TOP_K 必須為正整數") from exc
    assert top_k > 0, "LATTE_REVIEW_TOP_K 必須大於 0"
    return top_k


def _select_primary_rows(limit: Optional[int]) -> pd.DataFrame:
    payload = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for record in payload:
        metadata = record.get("metadata") or {}
        title = metadata.get("title") or ""
        summary = metadata.get("summary") or ""
        if "survey" in title.lower():
            continue
        rows.append(
            {
                "title": " ".join(title.split()),
                "abstract": " ".join(summary.split()),
                "metadata": metadata,
            }
        )
        if limit is not None and len(rows) >= limit:
            break
    if limit is not None and len(rows) < limit:
        raise AssertionError(f"找不到足夠的非 survey Speech LM 條目，僅取得 {len(rows)} 筆。")
    if not rows:
        raise AssertionError("找不到任何非 survey Speech LM 條目可供審查。")
    return pd.DataFrame(rows)


INCLUSION_CRITERIA = (
    "主題定義：口語語言模型（Speech Language Models, SLMs）指能直接以語音作為主要模態進行理解與生成的模型，逐步從傳統 ASR→LM→TTS 的串接式流程走向端到端或弱中介設計，以降低延遲、錯誤傳播並保留韻律/說話人等超語段資訊。\n\n近三年研究特別朝向全雙工口語語言模型（Full‑Duplex SLM, FD‑SLM）演進：模型在同一時刻同步聆聽與發聲，支援重疊語音、即時打斷與回饋，透過多流或單流的認知並行來協調時序與行為，並以時延、行為仲裁、語義連貫與聲學品質等多維度進行評估。 — 研究需明確以此範疇為核心，提出或分析 SLM/FD‑SLM 的架構、訓練或評估方法，並以語音作為主要互動模態。"
    " 研究焦點滿足下列任一者即可：（a）端到端 SpeechLM 或面向低延遲的串流/同步語音對話（包含全雙工同時聽說、重疊語音、即時打斷與回饋）；（b）語音表示自監督學習與離散語音 toke／神經編解碼器 token 在 SpeechLM 中的建模與使用；（c）語音與大型語言模型的整合方法（文字中介、潛在表示、音訊 token）與跨模態推理/多任務設計；（d）多維度評估與資源（例如時延、行為仲裁、語義連貫、聲學品質；或提供開源模型/數據/基準）。"
    "提供英文可評估性：需可取得英文全文或至少英文摘要與方法描述。"
)

EXCLUSION_CRITERIA = (
    "以神經音訊編解碼/壓縮為主要目標之研究（例如 EnCodec 類型），聚焦位元率與重建品質的音訊壓縮或語音合成可懂度評測，研究任務與評估指標不以語言建模或對話行為為中心。"
    "以語音增強、降噪、回聲消除或麥克風陣列信號處理為核心的工作（如 DNS Challenge 任務設定），其主要關注 PESQ、STOI、SI‑SDR 等聲學指標與前端處理，而非語音語言理解/生成或對話交互。"
    " 專注於語者克隆、語音風格/情感轉換等語音合成能力展示的研究（如 VALL‑E），研究目標為聲學表達與可模仿性，缺乏語音理解、對話策略或跨輪交互設計。"
"房間聲學/空間音訊建模與場景重建（如房響/聲場學習、Neural Acoustic Fields）之研究，關注空間化呈現與物理聲學重建，評估與方法論不屬於語言模型或對話系統範疇。"
)

# INCLUSION_CRITERIA = (
#     "論文需直接探討 speech language model 或 speech foundation model 的建構、訓練、應用或評估（包含 benchmarks）。"
#     " 若為多模態模型，必須包含語音作為主要模態之一。"
# )

# EXCLUSION_CRITERIA = (
#     "1. 需為英文論文。"
#     "2. 若研究僅涉及傳統 ASR/TTS 管線或一般 NLP 模型，且未對 speech language models 有實質貢獻則排除。"
#     " 3. 亦排除純理論討論、缺乏技術細節的新聞稿或無同行評審佐證的技術報告。"
# )


def _build_title_abstract_reviewer(
    name: str,
    model: str,
    *,
    model_args: dict[str, Any] = {},
    reasoning: str,
    backstory: str,
    additional_context: str | None = None,
) -> TitleAbstractReviewer:
    return TitleAbstractReviewer(
        name=name,
        provider=OpenAIProvider(model=model),
        inclusion_criteria=INCLUSION_CRITERIA,
        exclusion_criteria=EXCLUSION_CRITERIA,
        model_args=model_args,
        reasoning=reasoning,
        backstory=backstory,
        additional_context=additional_context,
        max_concurrent_requests=50,
        verbose=False,
    )


def _senior_filter(row: pd.Series) -> bool:
    eval_1 = row.get("round-A_JuniorNano_evaluation")
    eval_2 = row.get("round-A_JuniorMini_evaluation")
    if pd.isna(eval_1) or pd.isna(eval_2):
        return False
    try:
        score1 = int(eval_1)
        score2 = int(eval_2)
    except (TypeError, ValueError):
        return False

    if score1 != score2:
        if score1 >= 4 and score2 >= 4:
            return False
        if score1 >= 3 or score2 >= 3:
            return True
    elif score1 == score2 == 3:
        return True
    return False


def _derive_verdict(row: pd.Series) -> str:
    senior_eval = row.get("round-B_SeniorLead_evaluation")
    source = "junior"
    score: int | None = None

    if senior_eval is not None and not pd.isna(senior_eval):
        try:
            score = int(senior_eval)
            source = "senior"
        except (TypeError, ValueError):  # pragma: no cover - 防呆
            score = None

    if score is None:
        candidates: list[int] = []
        for value in (
            row.get("round-A_JuniorNano_evaluation"),
            row.get("round-A_JuniorMini_evaluation"),
        ):
            if value is None or pd.isna(value):
                continue
            try:
                candidates.append(int(value))
            except (TypeError, ValueError):  # pragma: no cover - 防呆
                continue
        if candidates:
            score = round(sum(candidates) / len(candidates))

    if score is None:
        return "未知"  # 資料缺失

    if score >= 4:
        decision = "納入"
    elif score <= 2:
        decision = "排除"
    else:
        decision = "需再評估"

    return f"{decision} (來源: {source}, 評分: {score})"


def _sanitize_value(value: object) -> object:
    try:
        if pd.isna(value):  # type: ignore[arg-type]
            return None
    except TypeError:
        pass
    return value


def test_three_reviewer_workflow_for_speech_language_models() -> None:
    _require_openai_key()
    top_k = _resolve_top_k()
    df = _select_primary_rows(top_k)

    junior_nano = _build_title_abstract_reviewer(
        "JuniorNano",
        "gpt-5-nano",
        model_args={'reasoning_effort': REASONING_EFFORT},
        reasoning="brief",
        backstory="一位專注於 speech foundation model 文獻整理的資深博士生",
    )
    junior_mini = _build_title_abstract_reviewer(
        "JuniorMini",
        "gpt-4.1-mini",
        reasoning="brief",
        backstory="一位熟悉語音與大型語言模型交叉領域的研究助理",
    )
    senior = _build_title_abstract_reviewer(
        "SeniorLead",
        "gpt-5-mini",
        model_args={'reasoning_effort': REASONING_EFFORT},
        reasoning="brief",
        backstory="負責統整 speech language model 新知的首席研究員",
        additional_context="""
        兩位 junior reviewer 已提供初步評估，請在整合意見前檢視他們的回饋。
        """.strip(),
    )

    workflow_schema = [
        {
            "round": "A",
            "reviewers": [junior_nano, junior_mini],
            "text_inputs": ["title", "abstract"],
        },
        {
            "round": "B",
            "reviewers": [senior],
            "text_inputs": [
                "title",
                "abstract",
                "round-A_JuniorNano_output",
                "round-A_JuniorNano_evaluation",
                "round-A_JuniorMini_output",
                "round-A_JuniorMini_evaluation",
            ],
            "filter": _senior_filter,
        },
    ]

    workflow = ReviewWorkflow.model_validate(
        {"workflow_schema": workflow_schema, "verbose": False},
        context={"data": df},
    )

    result_df = asyncio.run(workflow.run(df))
    needs_senior = result_df.apply(_senior_filter, axis=1).astype(bool)

    result_df["final_verdict"] = result_df.apply(_derive_verdict, axis=1)

    output_records: list[dict[str, object]] = []
    for index, row in result_df.iterrows():
        record = {column: _sanitize_value(row[column]) for column in result_df.columns}
        metadata_value = row.get("metadata") if "metadata" in row else None
        if metadata_value is None:
            metadata_value = df.loc[index, "metadata"]
        record["metadata"] = metadata_value
        output_records.append(record)

    if top_k is None:
        output_filename = "latte_review_results_step5_full.json"
    else:
        output_filename = f"latte_review_results_step5_top{len(output_records)}.json"
    output_path = OUTPUT_DIR / output_filename
    output_path.write_text(json.dumps(output_records, ensure_ascii=False, indent=2), encoding="utf-8")

    assert output_path.exists(), "結果輸出檔案未成功建立"
    assert len(output_records) == len(df), "輸出筆數需與輸入筆數一致"

    for index in range(len(df)):
        for reviewer in (junior_nano, junior_mini):
            base = f"round-A_{reviewer.name}"
            assert result_df.loc[index, f"{base}_output"], f"{base}_output 應包含模型回應"
            evaluation = result_df.loc[index, f"{base}_evaluation"]
            assert isinstance(evaluation, int), f"{base}_evaluation 應為整數"
            assert 1 <= evaluation <= 5, f"{base}_evaluation 應介於 1 至 5，得到 {evaluation}"
            reasoning = result_df.loc[index, f"{base}_reasoning"]
            assert isinstance(reasoning, str) and reasoning.strip(), f"{base}_reasoning 應提供文字理由"

        senior_base = "round-B_SeniorLead"
        senior_eval_col = f"{senior_base}_evaluation"
        senior_output_col = f"{senior_base}_output"

        if senior_eval_col not in result_df.columns:
            assert not needs_senior.any(), "需要複審時應產生 Round B 欄位"
            continue

        senior_eval = result_df.loc[index, senior_eval_col]
        senior_output = result_df.loc[index, senior_output_col]

        if not needs_senior.iloc[index]:
            assert pd.isna(senior_eval), "未觸發複審時，Senior 評分應為 NaN"
            assert pd.isna(senior_output), "未觸發複審時，Senior 輸出應為 NaN"
            verdict = result_df.loc[index, "final_verdict"]
            assert isinstance(verdict, str) and verdict.strip(), "final_verdict 應為非空字串"
            continue

        assert isinstance(senior_eval, int) and 1 <= senior_eval <= 5, f"{senior_base}_evaluation 應為 1~5"
        if isinstance(senior_output, str):
            assert senior_output.strip(), "Senior 回應內容不可為空"
        else:
            assert isinstance(senior_output, dict) and senior_output, "Senior 回應內容不可為空"
        senior_reasoning = result_df.loc[index, f"{senior_base}_reasoning"]
        assert isinstance(senior_reasoning, str) and senior_reasoning.strip(), "Senior 必須提供理由"

        verdict = result_df.loc[index, "final_verdict"]
        assert isinstance(verdict, str) and verdict.strip(), "final_verdict 應為非空字串"

        metadata = result_df.loc[index, "metadata"]
        assert isinstance(metadata, dict) and metadata, "metadata 欄位必須保留原始資訊"
