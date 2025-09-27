"""Environment loading helpers for API integrations."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv as _dotenv_load
except ImportError:  # pragma: no cover - optional dependency
    _dotenv_load = None


def load_env_file(dotenv_path: Optional[Path] = None, *, override: bool = False) -> None:
    """Load environment variables from ``.env`` into ``os.environ``.

    Parameters
    ----------
    dotenv_path:
        Explicit location of the environment file. Defaults to ``Path.cwd() / ".env"``.
    override:
        When ``True`` any existing environment variables are overwritten.
    """

    path = dotenv_path or Path.cwd() / ".env"

    if _dotenv_load is not None:
        _dotenv_load(dotenv_path=path, override=override)
        return

    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value


__all__ = ["load_env_file"]
