"""Title normalization helpers for reference matching."""

from __future__ import annotations

import re
import unicodedata


_TEX_SPECIAL_REPLACEMENTS = {
    r"\&": " and ",
    r"\%": " percent ",
    r"\_": " ",
    r"\#": " ",
    r"\$": " ",
    r"\{": "",
    r"\}": "",
    "~": " ",
    "@": " at ",
    "&": " and ",
}


def _strip_outer_wrappers(text: str) -> str:
    """Remove outermost braces or quotes repeatedly."""
    text = text.strip()
    changed = True
    while changed:
        changed = False
        if len(text) >= 2 and text[0] == "{" and text[-1] == "}":
            text = text[1:-1].strip()
            changed = True
        elif len(text) >= 2 and text[0] == '"' and text[-1] == '"':
            text = text[1:-1].strip()
            changed = True
    return text


def _remove_tex_commands(text: str) -> str:
    """Drop TeX commands while keeping their arguments for later cleanup."""
    return re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", text)


def normalize_title(text: str) -> str:
    """Normalize a title string for matching."""
    if text is None:
        return ""

    cleaned = _strip_outer_wrappers(text)

    for needle, replacement in _TEX_SPECIAL_REPLACEMENTS.items():
        cleaned = cleaned.replace(needle, replacement)

    cleaned = _remove_tex_commands(cleaned)
    cleaned = cleaned.replace("$", " ")
    cleaned = cleaned.replace("{", "").replace("}", "")

    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = cleaned.encode("ascii", "ignore").decode("ascii")

    cleaned = cleaned.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def split_words(text: str) -> list[str]:
    """Split a normalized title into tokens."""
    normalized = normalize_title(text)
    if not normalized:
        return []
    return normalized.split()
