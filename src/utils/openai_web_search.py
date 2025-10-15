"""OpenAI web search helpers built on top of the shared LLM provider layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union, Literal

from .llm import LLMResult, LLMService, OpenAIProvider

Message = Dict[str, Any]
MessageInput = Union[str, Sequence[Message]]
SearchContextSize = Literal["low", "medium", "high"]


@dataclass
class WebSearchOptions:
    """Configuration block for an OpenAI web search tool call."""

    allowed_domains: Optional[Sequence[str]] = None
    search_context_size: SearchContextSize = "medium"
    user_location: Optional[Dict[str, Any]] = None
    tool_type: str = "web_search"
    _allowed_tool_types: Iterable[str] = field(
        default_factory=lambda: ("web_search", "web_search_2025_08_26"),
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        tool_type_normalized = self.tool_type.strip().lower()
        if tool_type_normalized not in {t.lower() for t in self._allowed_tool_types}:
            raise ValueError("tool_type must be one of {'web_search', 'web_search_2025_08_26'}")
        self.tool_type = tool_type_normalized
        if self.search_context_size not in {"low", "medium", "high"}:
            raise ValueError("search_context_size must be 'low', 'medium', or 'high'")
        if self.user_location is not None:
            self.user_location = {
                key: value
                for key, value in self.user_location.items()
                if value is not None
            }

    def to_tool_param(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"type": self.tool_type}
        if self.allowed_domains:
            deduped = list(dict.fromkeys(domain.strip() for domain in self.allowed_domains if domain.strip()))
            if deduped:
                payload["filters"] = {"allowed_domains": deduped}
        if self.search_context_size != "medium":
            payload["search_context_size"] = self.search_context_size
        if self.user_location:
            location_payload = dict(self.user_location)
            location_payload.setdefault("type", "approximate")
            payload["user_location"] = location_payload
        return payload


class OpenAIWebSearchProvider(OpenAIProvider):
    """OpenAI provider variant that surfaces the web search tool."""

    _EXTRA_ALLOWED_KEYS = {"tools", "tool_choice", "max_tool_calls", "parallel_tool_calls"}

    def _build_chat_kwargs(self, model: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        base_kwargs = super()._build_chat_kwargs(model, kwargs)
        for key in self._EXTRA_ALLOWED_KEYS:
            value = kwargs.get(key)
            if value is not None:
                base_kwargs[key] = value
        return base_kwargs

    def chat_with_web_search(
        self,
        model: str,
        messages: MessageInput,
        *,
        options: Optional[WebSearchOptions] = None,
        force_tool: bool = True,
        **kwargs: Any,
    ) -> LLMResult:
        tool_options = options or WebSearchOptions()
        tool_payload = tool_options.to_tool_param()
        merged_tools: List[Dict[str, Any]] = list(kwargs.pop("tools", []) or [])
        merged_tools.append(tool_payload)
        if force_tool and "tool_choice" not in kwargs:
            kwargs["tool_choice"] = "required"
        return super().chat(model, messages, tools=merged_tools, **kwargs)


def create_web_search_service(**provider_kwargs: Any) -> LLMService:
    """Construct an ``LLMService`` with an ``OpenAIWebSearchProvider`` for convenience."""

    provider = OpenAIWebSearchProvider(**provider_kwargs)
    return LLMService(providers={"openai": provider})


def ask_with_web_search(
    prompt: str,
    *,
    model: str = "gpt-4o",
    service: Optional[LLMService] = None,
    options: Optional[WebSearchOptions] = None,
    force_tool: bool = True,
    **kwargs: Any,
) -> LLMResult:
    """Shortcut helper to ask a single-turn question with web search enabled."""

    svc = service or create_web_search_service()
    provider = svc.get_provider("openai")
    if not isinstance(provider, OpenAIWebSearchProvider):
        raise TypeError("Provided LLMService is not configured with OpenAIWebSearchProvider")
    return provider.chat_with_web_search(
        model,
        [{"role": "user", "content": prompt}],
        options=options,
        force_tool=force_tool,
        **kwargs,
    )


__all__ = [
    "OpenAIWebSearchProvider",
    "WebSearchOptions",
    "create_web_search_service",
    "ask_with_web_search",
]
