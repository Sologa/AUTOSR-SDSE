from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.env import load_env_file

DEFAULT_CODEX_DISABLE_FLAGS = ["--disable", "web_search_request"]
GEMINI_WEB_SEARCH_TOOL = "google_web_search"

_REPO_ROOT_ENV = os.getenv("AUTOSR_REPO_ROOT")
REPO_ROOT = (
    Path(_REPO_ROOT_ENV).expanduser().resolve()
    if _REPO_ROOT_ENV
    else Path(__file__).resolve().parents[3]
)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def repo_root() -> Path:
    """Return the repository root path, with AUTOSR_REPO_ROOT override support."""
    return REPO_ROOT


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


def build_run_id() -> str:
    """Generate a run_id timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


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


def parse_json_snippet(response_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
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


def gemini_settings_path(root: Optional[Path] = None) -> Path:
    """Return the repo-local Gemini CLI settings.json path."""
    base = root or repo_root()
    return base / ".gemini" / "settings.json"


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


def _apply_gemini_context_policy(
    settings: Dict[str, Any],
    *,
    respect_git_ignore: Optional[bool],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Apply context.fileFiltering settings and return updated settings plus policy."""
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

    policy = {
        "respect_git_ignore": bool(respect_git_ignore),
    }
    return updated_settings, policy


def prepare_gemini_settings(
    *,
    root: Optional[Path],
    allow_web_search: bool,
    respect_git_ignore: Optional[bool] = None,
) -> Dict[str, Any]:
    """Apply repo-local Gemini settings for tool and file-filter control."""
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
    updated, context_policy = _apply_gemini_context_policy(
        updated,
        respect_git_ignore=respect_git_ignore,
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
            **context_policy,
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


__all__ = [
    "DEFAULT_CODEX_DISABLE_FLAGS",
    "GEMINI_WEB_SEARCH_TOOL",
    "build_run_id",
    "gemini_settings_path",
    "load_env",
    "parse_json_snippet",
    "prepare_gemini_settings",
    "read_json",
    "repo_root",
    "resolve_codex_bin",
    "restore_gemini_settings",
    "run_codex_exec",
    "update_manifest",
    "write_json",
]
