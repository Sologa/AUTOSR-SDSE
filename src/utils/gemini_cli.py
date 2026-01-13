from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.codex_cli import parse_json_snippet

GEMINI_WEB_SEARCH_TOOL = "google_web_search"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def gemini_settings_path(root: Optional[Path] = None) -> Path:
    """Return the repo-local Gemini settings.json path."""
    base = root or _repo_root()
    return base / ".gemini" / "settings.json"


def _normalize_tool_list(value: Any) -> List[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str) and value.strip():
        items = [value.strip()]
    else:
        items = []
    seen: set[str] = set()
    result: List[str] = []
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


def _apply_gemini_context_policy(
    settings: Dict[str, Any],
    *,
    respect_git_ignore: Optional[bool],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if respect_git_ignore is None:
        return settings, {}

    context = settings.get("context")
    context_payload = context if isinstance(context, dict) else {}
    file_filtering = context_payload.get("fileFiltering")
    file_payload = file_filtering if isinstance(file_filtering, dict) else {}

    updated_file_filtering = dict(file_payload)
    updated_file_filtering["respectGitIgnore"] = bool(respect_git_ignore)

    updated_context = dict(context_payload)
    updated_context["fileFiltering"] = updated_file_filtering

    updated_settings = dict(settings)
    updated_settings["context"] = updated_context

    policy = {"respect_git_ignore": bool(respect_git_ignore)}
    return updated_settings, policy


def prepare_gemini_settings(
    *,
    root: Optional[Path],
    allow_web_search: bool,
    respect_git_ignore: Optional[bool] = None,
) -> Dict[str, Any]:
    settings_path = gemini_settings_path(root)
    existed = settings_path.exists()
    original: Dict[str, Any] = {}
    if existed:
        loaded = _read_json(settings_path)
        if not isinstance(loaded, dict):
            raise ValueError("Gemini settings.json must be a JSON object")
        original = loaded

    updated, core, exclude = _apply_gemini_tool_policy(
        original,
        allow_web_search=allow_web_search,
    )
    updated, context_policy = _apply_gemini_context_policy(
        updated,
        respect_git_ignore=respect_git_ignore,
    )
    changed = updated != original
    if changed:
        _write_json(settings_path, updated)

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
            **context_policy,
        },
    }


def restore_gemini_settings(state: Dict[str, Any]) -> None:
    if not state.get("changed"):
        return
    settings_path = state.get("path")
    if not isinstance(settings_path, Path):
        return
    if state.get("existed"):
        original = state.get("original")
        if isinstance(original, dict):
            _write_json(settings_path, original)
    else:
        if settings_path.exists():
            settings_path.unlink()


def run_gemini_cli(
    prompt: str,
    model: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], str, Optional[str], Optional[str]]:
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

    parsed, snippet = parse_json_snippet(response_text)
    if parsed is None:
        return None, response_text, "gemini response is not valid JSON", model_used

    return parsed, response_text, None, model_used


__all__ = [
    "GEMINI_WEB_SEARCH_TOOL",
    "gemini_settings_path",
    "prepare_gemini_settings",
    "restore_gemini_settings",
    "run_gemini_cli",
]
