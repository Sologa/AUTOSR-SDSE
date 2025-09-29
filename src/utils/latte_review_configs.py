"""Utilities for loading LatteReview reviewer configuration data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_DEFAULT_PROFILE_KEY = "default"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _config_path() -> Path:
    return _repo_root() / "data" / "latte_review" / "title_abstract_reviewer_profiles.json"


def _normalize_key(value: str) -> str:
    return " ".join(value.split()).casefold()


@dataclass(frozen=True)
class TitleAbstractReviewerProfile:
    """Represents reviewer configuration for LatteReview TitleAbstract workflows."""

    key: str
    review_topic: str
    inclusion_criteria: str
    exclusion_criteria: str
    backstory: str
    reasoning: str
    additional_context: str
    examples: List[str] = field(default_factory=list)
    provider_model: Optional[str] = None
    provider_model_args: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    search_terms: Dict[str, List[str]] = field(default_factory=dict)

    def matches(self, topic: str) -> bool:
        normalized = _normalize_key(topic)
        candidate_keys = [self.key, *_ensure_iterable(self.aliases)]
        for item in candidate_keys:
            if not item:
                continue
            normalized_item = _normalize_key(str(item))
            if normalized == normalized_item:
                return True
            if normalized_item in normalized or normalized in normalized_item:
                return True
        return False

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "review_topic": self.review_topic,
            "inclusion_criteria": self.inclusion_criteria,
            "exclusion_criteria": self.exclusion_criteria,
            "backstory": self.backstory,
            "reasoning": self.reasoning,
            "additional_context": self.additional_context,
        }
        if self.examples:
            payload["examples"] = list(self.examples)
        if self.provider_model:
            payload["provider"] = {
                "model": self.provider_model,
                "model_args": self.provider_model_args or {},
            }
        if self.keywords:
            payload["keywords"] = list(self.keywords)
        if self.search_terms:
            payload["search_terms"] = {
                category: list(terms)
                for category, terms in self.search_terms.items()
            }
        return payload


def _ensure_iterable(values: Optional[Iterable[str]]) -> List[str]:
    if not values:
        return []
    return [str(item) for item in values]


@lru_cache(maxsize=1)
def load_title_abstract_profiles() -> Dict[str, TitleAbstractReviewerProfile]:
    config_file = _config_path()
    if not config_file.exists():
        raise FileNotFoundError(
            "TitleAbstract reviewer profile configuration not found: " f"{config_file}"
        )

    data = json.loads(config_file.read_text(encoding="utf-8"))
    profiles: Dict[str, TitleAbstractReviewerProfile] = {}
    for key, raw in data.items():
        def _clean_list(values: Iterable[Any]) -> List[str]:
            return [str(item).strip() for item in values if str(item).strip()]

        def _clean_mapping(mapping: Dict[str, Any]) -> Dict[str, List[str]]:
            result: Dict[str, List[str]] = {}
            for cat, values in mapping.items():
                if not values:
                    continue
                cleaned = _clean_list(values if isinstance(values, list) else [values])
                if cleaned:
                    result[str(cat).strip()] = cleaned
            return result

        profile = TitleAbstractReviewerProfile(
            key=_normalize_key(key),
            review_topic=str(raw.get("review_topic", "")).strip(),
            inclusion_criteria=str(raw.get("inclusion_criteria", "")).strip(),
            exclusion_criteria=str(raw.get("exclusion_criteria", "")).strip(),
            backstory=str(raw.get("backstory", "")).strip(),
            reasoning=str(raw.get("reasoning", "")).strip() or "brief",
            additional_context=str(raw.get("additional_context", "")).strip(),
            examples=_clean_list(raw.get("examples", [])),
            provider_model=str(raw.get("provider", {}).get("model", "")).strip() or None,
            provider_model_args={
                str(k): v for k, v in raw.get("provider", {}).get("model_args", {}).items()
            },
            aliases=_clean_list(raw.get("aliases", [])),
            keywords=_clean_list(raw.get("keywords", [])),
            search_terms=_clean_mapping(raw.get("search_terms", {})),
        )
        profiles[profile.key] = profile
    return profiles


def get_title_abstract_profile(topic: Optional[str]) -> TitleAbstractReviewerProfile:
    profiles = load_title_abstract_profiles()
    if not profiles:
        raise ValueError("No TitleAbstract reviewer profiles are configured")

    if topic:
        for profile in profiles.values():
            if profile.matches(topic):
                return profile

    default_profile = profiles.get(_normalize_key(_DEFAULT_PROFILE_KEY))
    if not default_profile:
        raise ValueError("Default TitleAbstract reviewer profile is not defined in configuration")
    return default_profile


__all__ = [
    "TitleAbstractReviewerProfile",
    "get_title_abstract_profile",
    "load_title_abstract_profiles",
]
