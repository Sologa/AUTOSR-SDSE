from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from src.utils.keyword_extractor import ExtractParams, build_generate_instructions
from src.utils.paper_downloaders import fetch_arxiv_metadata
from src.utils.paper_workflows import trim_arxiv_id

SHARED_DIR = Path(__file__).resolve().parents[1] / "test-shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

_codex_utils = importlib.import_module("codex_cli_utils")
DEFAULT_CODEX_DISABLE_FLAGS = _codex_utils.DEFAULT_CODEX_DISABLE_FLAGS
build_run_id = _codex_utils.build_run_id
load_env = _codex_utils.load_env
parse_json_snippet = _codex_utils.parse_json_snippet
prepare_gemini_settings = _codex_utils.prepare_gemini_settings
read_json = _codex_utils.read_json
repo_root = _codex_utils.repo_root
resolve_codex_bin = _codex_utils.resolve_codex_bin
restore_gemini_settings = _codex_utils.restore_gemini_settings
run_codex_exec = _codex_utils.run_codex_exec
update_manifest = _codex_utils.update_manifest
write_json = _codex_utils.write_json

GEMINI_ENV_BLOCKLIST = (
    "OPENAI_API_KEY",
    "OPENAI_ORGANIZATION_ID",
    "SEMANTIC_SCHOLAR_API_KEY",
    "GITHUB_TOKEN",
)
_TERM_INVALID_CHARS = re.compile(r"[^0-9A-Za-z /-]+")
_TERM_MULTI_SPACES = re.compile(r"\\s{2,}")


def build_gemini_env() -> Dict[str, str]:
    """Return a subprocess environment with Gemini-safe variables."""
    env = os.environ.copy()
    for key in GEMINI_ENV_BLOCKLIST:
        env.pop(key, None)
    return env


def slugify_topic(text: str) -> str:
    """Create a filesystem-friendly slug for a topic string."""
    base = "".join(
        "_" if not (ch.isalnum() or "\u4e00" <= ch <= "\u9fff") else ch
        for ch in text.strip()
    )
    base = "_".join(filter(None, base.split("_")))
    return base.lower() or "topic"


def _sanitize_search_term(value: str, *, max_words: int = 3) -> Optional[str]:
    """Normalize a search term to match prompt constraints."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    text = text.replace("_", " ")
    text = _TERM_INVALID_CHARS.sub(" ", text)
    text = _TERM_MULTI_SPACES.sub(" ", text)
    text = text.strip(" ,.;:|/")
    if not text:
        return None
    words = text.split()
    if len(words) > max_words:
        words = words[:max_words]
    cleaned = " ".join(words).lower().strip()
    return cleaned or None


def sanitize_search_terms(
    search_terms: Dict[str, List[str]],
    *,
    max_words: int = 3,
    min_terms_per_category: int = 1,
    max_total: Optional[int] = None,
) -> Dict[str, List[str]]:
    """Sanitize search term buckets while preserving category order."""
    cleaned: Dict[str, List[str]] = {}
    for category, values in search_terms.items():
        if not isinstance(category, str):
            continue
        bucket: List[str] = []
        seen: set[str] = set()
        for value in values or []:
            sanitized = _sanitize_search_term(value, max_words=max_words)
            if not sanitized:
                continue
            if sanitized in seen:
                continue
            seen.add(sanitized)
            bucket.append(sanitized)
        if len(bucket) >= min_terms_per_category:
            cleaned[category] = bucket
    if max_total is None:
        return cleaned

    trimmed: Dict[str, List[str]] = {}
    total = 0
    for category, values in cleaned.items():
        if total >= max_total:
            break
        remaining = max_total - total
        bucket = values[:remaining]
        if bucket:
            trimmed[category] = bucket
            total += len(bucket)
    return trimmed


def sanitize_search_terms_payload(
    payload: Dict[str, Any],
    *,
    max_words: int = 3,
    max_total: Optional[int] = None,
) -> Dict[str, Any]:
    """Apply search term sanitation to a payload object."""
    if not isinstance(payload, dict):
        return payload
    search_terms = payload.get("search_terms")
    if not isinstance(search_terms, dict):
        return payload
    updated = dict(payload)
    updated["search_terms"] = sanitize_search_terms(
        search_terms,
        max_words=max_words,
        max_total=max_total,
    )
    return updated


def load_pdf_paths(pdf_dir: Path, limit: int) -> Tuple[List[Path], List[str]]:
    """Load PDF paths from a directory with optional limit."""
    if not pdf_dir.exists():
        raise FileNotFoundError(f"PDF directory not found: {pdf_dir}")
    pdf_paths = sorted(path for path in pdf_dir.glob("*.pdf") if path.is_file())
    if limit and limit > 0:
        pdf_paths = pdf_paths[:limit]
    warnings: List[str] = []
    if not pdf_paths:
        warnings.append(f"No PDFs found under: {pdf_dir}")
    return pdf_paths, warnings


def _infer_arxiv_id(pdf_path: Path) -> str:
    """Infer the arXiv identifier from a PDF filename."""
    candidate = trim_arxiv_id(pdf_path.stem)
    if not candidate:
        raise ValueError(f"Unable to infer arXiv identifier from PDF name: {pdf_path}")
    return candidate


def collect_arxiv_metadata(pdf_paths: Sequence[Path]) -> List[Dict[str, str]]:
    """Collect arXiv metadata for each PDF path."""
    records: List[Dict[str, str]] = []
    session = requests.Session()
    try:
        for pdf_path in pdf_paths:
            arxiv_id = _infer_arxiv_id(pdf_path)
            metadata = fetch_arxiv_metadata(arxiv_id, session=session)
            title = (metadata.get("title") or "").strip()
            abstract = (metadata.get("summary") or metadata.get("abstract") or "").strip()
            if not title or not abstract:
                raise ValueError(f"Metadata for arXiv:{arxiv_id} missing title or abstract")
            published = (metadata.get("published") or "").strip()
            year = published.split("-", 1)[0] if published else "unknown"
            url = (metadata.get("landing_url") or f"https://arxiv.org/abs/{arxiv_id}").strip()
            records.append(
                {
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "abstract": abstract,
                    "year": year,
                    "url": url,
                    "pdf_path": str(pdf_path),
                }
            )
    finally:
        session.close()
    return records


def format_metadata_block(metadata_list: Sequence[Dict[str, str]]) -> str:
    """Format arXiv metadata as a prompt-friendly text block."""
    if not metadata_list:
        return "(no metadata provided)"
    lines: List[str] = []
    for idx, meta in enumerate(metadata_list, start=1):
        lines.extend(
            [
                f"--- Paper {idx} ---",
                f"source_id: arXiv:{meta['arxiv_id']}",
                f"title: {meta['title']}",
                f"abstract: {meta['abstract']}",
                f"year: {meta['year']}",
                f"url: {meta['url']}",
                f"pdf_path: {meta['pdf_path']}",
            ]
        )
    return "\n".join(lines)


def build_keywords_prompt(
    *,
    params: ExtractParams,
    metadata_block: str,
    pdf_text_blocks: Optional[List[Tuple[str, str]]] = None,
    pdf_paths: Optional[Sequence[Path]] = None,
) -> str:
    """Build the keyword extraction prompt, optionally embedding PDF text."""
    prompt = build_generate_instructions(params, metadata_block=metadata_block)

    if pdf_paths:
        prompt += "\n\nPDF paths (use read_file to read each PDF before answering):\n"
        for pdf_path in pdf_paths:
            prompt += f"- {pdf_path}\n"

    if pdf_text_blocks:
        prompt += "\n\nExtracted PDF text (pre-processed):\n"
        for label, text in pdf_text_blocks:
            prompt += f"\n--- {label} ---\n{text}\n"

    return prompt.strip()


def load_text_inputs(paths: Sequence[Path]) -> List[Tuple[str, str]]:
    """Load text inputs from files for Codex CLI runs."""
    blocks: List[Tuple[str, str]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        blocks.append((path.name, text))
    return blocks


def extract_pdf_text(pdf_paths: Sequence[Path], output_dir: Path) -> List[Path]:
    """Extract PDF text with pdfplumber and write one text file per PDF."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("pdfplumber is required; run `uv sync` before PDF-to-text extraction") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[Path] = []
    for pdf_path in pdf_paths:
        text_chunks: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text_chunks.append(page.extract_text() or "")
        output_path = output_dir / f"{pdf_path.stem}.txt"
        output_path.write_text("\n\n".join(text_chunks).strip() + "\n", encoding="utf-8")
        outputs.append(output_path)
    return outputs


def run_gemini_cli(
    prompt: str,
    model: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], str, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """Invoke Gemini CLI and parse JSON output, returning model/tool stats when available."""
    cmd = ["gemini", "--output-format", "json"]
    if model:
        cmd.extend(["--model", model])
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,
            check=False,
            env=build_gemini_env(),
        )
    except FileNotFoundError:
        return None, "", "gemini CLI not found", None, None

    if result.returncode != 0:
        return None, result.stdout.strip(), result.stderr.strip() or "gemini CLI failed", None, None

    raw = result.stdout.strip()
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError:
        return None, raw, "gemini output is not valid JSON", None, None

    response_text = None
    if isinstance(outer, dict):
        response_text = outer.get("response")
    if not isinstance(response_text, str):
        return None, raw, "gemini JSON missing response field", None, None

    model_used = None
    tool_usage = None
    stats = outer.get("stats") if isinstance(outer, dict) else None
    if isinstance(stats, dict):
        models = stats.get("models")
        if isinstance(models, dict) and models:
            model_used = ",".join(models.keys())
        tools = stats.get("tools")
        if isinstance(tools, dict):
            tool_usage = tools

    parsed, snippet = parse_json_snippet(response_text)
    if parsed is None:
        return None, response_text, "gemini response is not valid JSON", model_used, tool_usage

    return parsed, response_text, None, model_used, tool_usage


def init_manifest(
    output_dir: Path,
    run_id: str,
    topic: str,
    input_pdfs: Sequence[Path],
    prompt_path: Path,
    input_pdf_dir: Optional[Path],
) -> Dict[str, Any]:
    """Load or initialize the run manifest for a given run_id."""
    manifest_path = output_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        if isinstance(manifest, dict):
            return manifest
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "topic": topic,
        "input_pdf_dir": str(input_pdf_dir) if input_pdf_dir else None,
        "input_pdfs": [str(path) for path in input_pdfs],
        "prompt_path": str(prompt_path),
        "outputs": [],
        "commands": [],
    }
    write_json(manifest_path, manifest)
    return manifest
