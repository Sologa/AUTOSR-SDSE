from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.env import load_env_file

DEFAULT_INCLUSION = "論文需與指定主題高度相關，且提供可用於評估的英文內容（全文或摘要/方法）。"
DEFAULT_EXCLUSION = "論文若與主題無關，或缺乏可判斷的英文題名/摘要/方法描述則排除。"
DEFAULT_CODEX_DISABLE_FLAGS = ["--disable", "web_search_request"]
GEMINI_WEB_SEARCH_TOOL = "google_web_search"


def repo_root() -> Path:
    """Return the repository root path used by the test utilities."""
    return REPO_ROOT


def gemini_settings_path(root: Optional[Path] = None) -> Path:
    """Return the repo-local Gemini CLI settings.json path."""
    base = root or repo_root()
    return base / ".gemini" / "settings.json"


def load_env() -> None:
    """Load environment variables from the repo-level .env file."""
    load_env_file(repo_root() / ".env")


def resolve_codex_bin(explicit: Optional[str] = None) -> str:
    """Resolve the Codex CLI binary path with explicit/env/Homebrew fallback."""
    if explicit:
        return explicit
    env_path = os.getenv("CODEX_BIN")
    if env_path:
        return env_path
    homebrew = Path("/opt/homebrew/bin/codex")
    if homebrew.exists():
        return str(homebrew)
    return "codex"


def read_json(path: Path) -> Any:
    """Read a JSON file from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    """Write JSON to disk, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_tool_list(value: Any) -> List[str]:
    """Normalize tool list inputs to a de-duplicated list of strings."""
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str) and value.strip():
        items = [value.strip()]
    else:
        items = []
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _apply_gemini_tool_policy(
    settings: Dict[str, Any],
    *,
    allow_web_search: bool,
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """Apply Gemini tool policy updates and return updated settings plus tools lists."""
    tools = settings.get("tools")
    tools_payload = tools if isinstance(tools, dict) else {}
    core = _normalize_tool_list(tools_payload.get("core"))
    exclude = _normalize_tool_list(tools_payload.get("exclude"))

    if allow_web_search:
        if core and GEMINI_WEB_SEARCH_TOOL not in core:
            core.append(GEMINI_WEB_SEARCH_TOOL)
        if GEMINI_WEB_SEARCH_TOOL in exclude:
            exclude = [item for item in exclude if item != GEMINI_WEB_SEARCH_TOOL]
    else:
        if GEMINI_WEB_SEARCH_TOOL in core:
            core = [item for item in core if item != GEMINI_WEB_SEARCH_TOOL]
        if GEMINI_WEB_SEARCH_TOOL not in exclude:
            exclude.append(GEMINI_WEB_SEARCH_TOOL)

    updated_tools: Dict[str, Any] = dict(tools_payload)
    if core:
        updated_tools["core"] = core
    else:
        updated_tools.pop("core", None)
    if exclude:
        updated_tools["exclude"] = exclude
    else:
        updated_tools.pop("exclude", None)

    updated_settings = dict(settings)
    if updated_tools:
        updated_settings["tools"] = updated_tools
    else:
        updated_settings.pop("tools", None)
    return updated_settings, core, exclude


def prepare_gemini_settings(*, root: Optional[Path], allow_web_search: bool) -> Dict[str, Any]:
    """Apply repo-local Gemini settings for web search control and return state."""
    settings_path = gemini_settings_path(root)
    existed = settings_path.exists()
    original: Dict[str, Any] = {}
    if existed:
        loaded = read_json(settings_path)
        if not isinstance(loaded, dict):
            raise ValueError("Gemini settings.json must be a JSON object")
        original = loaded

    updated, core, exclude = _apply_gemini_tool_policy(
        original,
        allow_web_search=allow_web_search,
    )
    changed = updated != original
    if changed:
        write_json(settings_path, updated)

    return {
        "path": settings_path,
        "existed": existed,
        "original": original,
        "changed": changed,
        "policy": {
            "settings_path": str(settings_path),
            "allow_web_search": allow_web_search,
            "tools_core": core,
            "tools_exclude": exclude,
            "modified": changed,
        },
    }


def restore_gemini_settings(state: Dict[str, Any]) -> None:
    """Restore Gemini settings.json to its original state when modified."""
    if not state.get("changed"):
        return
    settings_path = state.get("path")
    if not isinstance(settings_path, Path):
        return
    if state.get("existed"):
        original = state.get("original")
        if isinstance(original, dict):
            write_json(settings_path, original)
    else:
        if settings_path.exists():
            settings_path.unlink()


def build_run_id() -> str:
    """Generate a run_id timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_arxiv_items(path: Path, limit: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Load and normalize arXiv metadata entries, returning items and warnings."""
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError("arXiv metadata payload must be a list")

    items: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for idx, entry in enumerate(payload[:limit]):
        if not isinstance(entry, dict):
            warnings.append(f"entry[{idx}] is not an object")
            continue
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        arxiv_id = str(
            metadata.get("arxiv_id")
            or entry.get("arxiv_id")
            or entry.get("id")
            or ""
        ).strip()
        title = str(
            metadata.get("title")
            or entry.get("title")
            or entry.get("search_record", {}).get("title")
            or ""
        ).strip()
        abstract = str(
            metadata.get("summary")
            or metadata.get("abstract")
            or entry.get("summary")
            or entry.get("abstract")
            or entry.get("search_record", {}).get("summary")
            or ""
        ).strip()
        missing_fields = []
        if not title:
            missing_fields.append("title")
        if not abstract:
            missing_fields.append("abstract")
        items.append(
            {
                "index": idx,
                "arxiv_id": arxiv_id,
                "title": title,
                "abstract": abstract,
                "metadata": metadata,
                "missing_fields": missing_fields,
            }
        )

    return items, warnings


def criteria_payload_to_strings(payload: Dict[str, Any]) -> Tuple[str, str]:
    """Convert criteria payload into inclusion/exclusion strings."""
    topic_definition = str(payload.get("topic_definition") or "").strip()
    inclusion = payload.get("inclusion_criteria")
    exclusion = payload.get("exclusion_criteria")

    inclusion_lines: List[str] = []
    if topic_definition:
        inclusion_lines.append(f"主題定義：{topic_definition}")

    if isinstance(inclusion, dict):
        required = inclusion.get("required") or []
        any_of = inclusion.get("any_of") or []
        if isinstance(required, list):
            for item in required:
                if not isinstance(item, dict):
                    continue
                criterion = str(item.get("criterion") or "").strip()
                if criterion:
                    inclusion_lines.append(criterion)
        if isinstance(any_of, list) and any_of:
            inclusion_lines.append("以下群組每組至少滿足一項：")
            for group in any_of:
                if not isinstance(group, dict):
                    continue
                label = str(group.get("label") or "").strip() or "群組"
                options = group.get("options") or []
                option_lines: List[str] = []
                if isinstance(options, list):
                    for opt in options:
                        if not isinstance(opt, dict):
                            continue
                        criterion = str(opt.get("criterion") or "").strip()
                        if criterion:
                            option_lines.append(f"- {criterion}")
                if option_lines:
                    inclusion_lines.append(f"{label}:")
                    inclusion_lines.extend(option_lines)

    exclusion_lines: List[str] = []
    if isinstance(exclusion, list):
        for item in exclusion:
            if not isinstance(item, dict):
                continue
            criterion = str(item.get("criterion") or "").strip()
            if criterion:
                exclusion_lines.append(criterion)
    elif isinstance(exclusion, str):
        exclusion_lines.append(exclusion.strip())

    inclusion_text = "\n".join(line for line in inclusion_lines if line)
    exclusion_text = "\n".join(line for line in exclusion_lines if line)
    return inclusion_text, exclusion_text


def load_criteria(criteria_path: Optional[Path]) -> Tuple[str, str, str, Optional[Path]]:
    """Load criteria data and return inclusion/exclusion text plus source metadata."""
    criteria_source = "default"
    criteria_payload: Dict[str, Any] = {}
    used_path: Optional[Path] = None

    if criteria_path and criteria_path.exists():
        loaded = read_json(criteria_path)
        if isinstance(loaded, dict):
            structured = loaded.get("structured_payload")
            if isinstance(structured, dict):
                criteria_payload = structured
                criteria_source = "workspace"
                used_path = criteria_path
            elif isinstance(loaded.get("topic_definition"), (str, dict, list)):
                criteria_payload = loaded
                criteria_source = "workspace"
                used_path = criteria_path

    inclusion, exclusion = criteria_payload_to_strings(criteria_payload)
    if not inclusion:
        inclusion = DEFAULT_INCLUSION
    if not exclusion:
        exclusion = DEFAULT_EXCLUSION
    return inclusion, exclusion, criteria_source, used_path


def format_text_inputs(pairs: List[Tuple[str, str]]) -> str:
    """Format key/value pairs into sectioned text blocks."""
    parts = []
    for key, value in pairs:
        parts.append(f"=== {key} ===\n{value}")
    return "\n\n".join(parts)


def build_review_prompt(item_text: str, inclusion: str, exclusion: str) -> str:
    """Build the review prompt with criteria and JSON-only output instructions."""
    reasoning_instruction = (
        "Provide a brief (1-sentence) explanation for your scoring. "
        "State your reasoning before giving the score."
    )
    prompt = f"""
**Review the title and abstract below and evaluate whether they should be included based on the following inclusion and exclusion criteria (if any).**
**Note that the study should be included only and only if it meets ALL inclusion criteria and NONE of the exclusion criteria.**

---

**Input item:**
<<{item_text}>>

---

**Inclusion criteria:**
{inclusion}

**Exclusion criteria:**
{exclusion}

---

**Instructions**

1. Output your evaluation as an integer between 1 and 5, where:
   - 1 means absolutely to exclude.
   - 2 means better to exclude.
   - 3 Not sure if to include or exclude.
   - 4 means better to include.
   - 5 means absolutely to include.
---

{reasoning_instruction}

Return a JSON object with keys "reasoning" (string) and "evaluation" (integer 1-5). Only output JSON.
""".strip()
    return prompt


def run_codex_exec(
    prompt: str,
    model: str,
    schema_path: Optional[Path],
    *,
    codex_bin: Optional[str] = None,
    codex_extra_args: Optional[List[str]] = None,
) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
    """Invoke `codex exec` and parse the JSON response."""
    cmd = [resolve_codex_bin(codex_bin), "exec"]
    if codex_extra_args:
        cmd.extend(codex_extra_args)
    cmd.append("-")
    cmd.extend(["--model", model])
    if schema_path:
        cmd.extend(["--output-schema", str(schema_path)])
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return None, "", "codex CLI not found"

    if result.returncode != 0:
        return None, result.stdout.strip(), result.stderr.strip() or "codex exec failed"

    raw = result.stdout.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None, raw, "codex output is not valid JSON"
    return parsed, raw, None


def _parse_json_snippet(response_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse JSON from text, falling back to a best-effort JSON snippet."""
    try:
        parsed = json.loads(response_text)
        return parsed, None
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None, None
        snippet = response_text[start : end + 1]
        try:
            parsed = json.loads(snippet)
            return parsed, snippet
        except json.JSONDecodeError:
            return None, snippet


def run_gemini_cli(prompt: str, model: Optional[str]) -> Tuple[Optional[Dict[str, Any]], str, Optional[str], Optional[str]]:
    """Invoke Gemini CLI and parse JSON output, returning model_used when available."""
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
        )
    except FileNotFoundError:
        return None, "", "gemini CLI not found", None

    if result.returncode != 0:
        return None, result.stdout.strip(), result.stderr.strip() or "gemini CLI failed", None

    raw = result.stdout.strip()
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError:
        return None, raw, "gemini output is not valid JSON", None

    response_text = None
    if isinstance(outer, dict):
        response_text = outer.get("response")
    if not isinstance(response_text, str):
        return None, raw, "gemini JSON missing response field", None

    model_used = None
    stats = outer.get("stats") if isinstance(outer, dict) else None
    if isinstance(stats, dict):
        models = stats.get("models")
        if isinstance(models, dict) and models:
            model_used = ",".join(models.keys())

    parsed, snippet = _parse_json_snippet(response_text)
    if parsed is None:
        return None, response_text, "gemini response is not valid JSON", model_used

    return parsed, response_text, None, model_used


def init_manifest(
    output_dir: Path,
    run_id: str,
    input_source: Path,
    criteria_source: str,
    criteria_path: Optional[Path],
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
        "input_source": str(input_source),
        "criteria_source": criteria_source,
        "criteria_path": str(criteria_path) if criteria_path else None,
        "outputs": [],
        "commands": [],
    }
    write_json(manifest_path, manifest)
    return manifest


def update_manifest(
    output_dir: Path,
    manifest: Dict[str, Any],
    *,
    name: str,
    path: Path,
    mode: str,
    provider: str,
    reviewer: Optional[str],
    model: Optional[str],
    command: List[str],
    command_meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Append output and command entries, then persist the manifest."""
    outputs = manifest.setdefault("outputs", [])
    outputs.append(
        {
            "name": name,
            "path": str(path),
            "mode": mode,
            "provider": provider,
            "reviewer": reviewer,
            "model": model,
        }
    )
    commands = manifest.setdefault("commands", [])
    command_entry = {
        "provider": provider,
        "command": " ".join(command),
        "model": model,
    }
    if command_meta:
        command_entry["tool_policy"] = command_meta
    commands.append(command_entry)
    write_json(output_dir / "run_manifest.json", manifest)
