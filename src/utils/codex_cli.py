from __future__ import annotations

import json
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from src.utils.env import load_env_file

DEFAULT_CODEX_DISABLE_FLAGS = ["--disable", "web_search_request"]
_REASONING_EFFORT_PATTERN = re.compile(r"^\s*model_reasoning_effort\s*=\s*.+$", re.MULTILINE)


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


def resolve_codex_home(explicit: Optional[Path] = None, *, repo_root: Optional[Path] = None) -> Optional[Path]:
    """Resolve CODEX_HOME from explicit path, env var, or repo-local .codex."""
    if explicit is not None:
        return Path(explicit)
    env_path = os.getenv("CODEX_HOME")
    if env_path:
        return Path(env_path)
    if repo_root:
        candidate = Path(repo_root) / ".codex"
        if candidate.exists():
            return candidate
    return None


def _patch_reasoning_effort(config_text: str, effort: str) -> str:
    updated = config_text.rstrip("\n")
    replacement = f'model_reasoning_effort = "{effort}"'
    if _REASONING_EFFORT_PATTERN.search(updated):
        updated = _REASONING_EFFORT_PATTERN.sub(replacement, updated)
        return f"{updated}\n"
    lines = updated.splitlines() if updated else []
    insert_at = 0
    for index, line in enumerate(lines):
        if line.strip().startswith("model "):
            insert_at = index + 1
            break
    lines.insert(insert_at, replacement)
    return "\n".join(lines).rstrip("\n") + "\n"


@contextmanager
def temporary_codex_config(
    *,
    codex_home: Optional[Path],
    reasoning_effort: Optional[str],
) -> Iterator[Optional[Path]]:
    """Temporarily update CODEX_HOME config to set model_reasoning_effort."""
    if not reasoning_effort or codex_home is None:
        yield codex_home
        return

    codex_home.mkdir(parents=True, exist_ok=True)
    config_path = codex_home / "config.toml"
    original: Optional[str] = None
    if config_path.exists():
        original = config_path.read_text(encoding="utf-8")

    updated = _patch_reasoning_effort(original or "", reasoning_effort)
    config_path.write_text(updated, encoding="utf-8")

    try:
        yield codex_home
    finally:
        if original is None:
            if config_path.exists():
                config_path.unlink()
        else:
            config_path.write_text(original, encoding="utf-8")


def _build_codex_env(codex_home: Optional[Path]) -> Dict[str, str]:
    env = os.environ.copy()
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    return env


def run_codex_exec(
    prompt: str,
    model: str,
    schema_path: Optional[Path],
    *,
    codex_bin: Optional[str] = None,
    codex_extra_args: Optional[Sequence[str]] = None,
    codex_home: Optional[Path] = None,
) -> Tuple[Optional[Dict[str, Any]], str, Optional[str], List[str]]:
    """Invoke `codex exec` and parse the JSON response."""
    load_env_file()

    cmd: List[str] = [resolve_codex_bin(codex_bin), "exec"]
    if codex_extra_args:
        cmd.extend(list(codex_extra_args))
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
            env=_build_codex_env(codex_home),
        )
    except FileNotFoundError:
        return None, "", "codex CLI not found", cmd

    if result.returncode != 0:
        return None, result.stdout.strip(), result.stderr.strip() or "codex exec failed", cmd

    raw = result.stdout.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None, raw, "codex output is not valid JSON", cmd
    if not isinstance(parsed, dict):
        return None, raw, "codex output JSON must be an object", cmd
    return parsed, raw, None, cmd


def parse_json_snippet(response_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse JSON from text, falling back to a best-effort JSON snippet."""
    try:
        parsed = json.loads(response_text)
        if isinstance(parsed, dict):
            return parsed, None
        return None, None
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None, None
        snippet = response_text[start : end + 1]
        try:
            parsed = json.loads(snippet)
        except json.JSONDecodeError:
            return None, snippet
        if not isinstance(parsed, dict):
            return None, snippet
        return parsed, snippet


__all__ = [
    "DEFAULT_CODEX_DISABLE_FLAGS",
    "parse_json_snippet",
    "resolve_codex_home",
    "resolve_codex_bin",
    "run_codex_exec",
    "temporary_codex_config",
]
