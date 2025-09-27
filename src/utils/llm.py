"""LLM provider abstraction layer with pricing, usage tracking, and provider implementations."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable, Dict, List, MutableMapping, Optional, Sequence, Tuple, Union

from openai import AsyncOpenAI, OpenAI

try:  # pragma: no cover - protective import for different SDK versions
    from openai import APIError, APITimeoutError, RateLimitError
except ImportError:  # pragma: no cover - fallback for unexpected SDK layout
    APIError = APITimeoutError = RateLimitError = Exception  # type: ignore

from .env import load_env_file


logger = logging.getLogger(__name__)

_ENV_LOADED = False
_COST_QUANTUM = Decimal("0.000001")


def ensure_env_loaded() -> None:
    """Load the local ``.env`` file once per process."""

    global _ENV_LOADED
    if not _ENV_LOADED:
        load_env_file()
        _ENV_LOADED = True


class LLMError(Exception):
    """Base exception for LLM related failures."""


class ProviderNotConfiguredError(LLMError):
    """Raised when a provider is not properly configured (e.g. missing credentials)."""


class UnknownModelError(LLMError):
    """Raised when a requested model is not present in the price table."""


class ProviderCallError(LLMError):
    """Raised when the provider returns a non-recoverable error."""


@dataclass(frozen=True)
class ModelPricing:
    """Pricing structure expressed as cost per 1M tokens."""

    input_cost_per_1m: float
    output_cost_per_1m: float


@dataclass
class LLMUsage:
    """Captures token usage and cost metadata for a call."""

    provider: str
    model: str
    mode: str
    input_tokens: int
    output_tokens: int
    cost: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResult:
    """High-level LLM invocation result."""

    content: str
    usage: LLMUsage
    raw_response: Any


class LLMUsageTracker:
    """Collects usage records for later inspection or reporting."""

    def __init__(self) -> None:
        self._records: List[LLMUsage] = []

    def add_record(self, record: LLMUsage) -> None:
        logger.debug("Recording LLM usage: %s", record)
        self._records.append(record)

    @property
    def records(self) -> Sequence[LLMUsage]:
        return tuple(self._records)

    def summarize(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        summary: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for record in self._records:
            key = (record.provider, record.model)
            if key not in summary:
                summary[key] = {
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost": 0.0,
                    "calls": 0,
                }
            summary_entry = summary[key]
            summary_entry["total_input_tokens"] += record.input_tokens
            summary_entry["total_output_tokens"] += record.output_tokens
            summary_entry["total_cost"] += record.cost
            summary_entry["calls"] += 1
        return summary


class ModelPriceRegistry:
    """Provides lookup for model pricing information."""

    def __init__(self, price_table: Optional[MutableMapping[str, MutableMapping[str, ModelPricing]]] = None) -> None:
        self._price_table: Dict[str, Dict[str, ModelPricing]] = (
            {provider: dict(models) for provider, models in price_table.items()}
            if price_table
            else {}
        )

    def register(self, provider: str, model: str, pricing: ModelPricing) -> None:
        self._price_table.setdefault(provider, {})[model] = pricing

    def get(self, provider: str, model: str) -> ModelPricing:
        try:
            return self._price_table[provider][model]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise UnknownModelError(f"Pricing for provider={provider} model={model} is not registered") from exc

    @property
    def table(self) -> Dict[str, Dict[str, ModelPricing]]:
        return {provider: dict(models) for provider, models in self._price_table.items()}


DEFAULT_PRICING = ModelPriceRegistry(
    price_table={
        "openai": {
            # OpenAI API pricing (USD per 1M tokens) cross-checked against https://openai.com/api/pricing
            # and individual model pages on https://platform.openai.com/docs/models (retrieved 2025-09-27).
            "gpt-5": ModelPricing(input_cost_per_1m=1.25, output_cost_per_1m=10.0),
            "gpt-5-mini": ModelPricing(input_cost_per_1m=0.25, output_cost_per_1m=2.0),
            "gpt-5-nano": ModelPricing(input_cost_per_1m=0.05, output_cost_per_1m=0.4),
            "gpt-4o": ModelPricing(input_cost_per_1m=2.5, output_cost_per_1m=10.0),
            "gpt-4o-mini": ModelPricing(input_cost_per_1m=0.6, output_cost_per_1m=2.4),
            "gpt-4.1": ModelPricing(input_cost_per_1m=2.0, output_cost_per_1m=8.0),
            "gpt-4.1-mini": ModelPricing(input_cost_per_1m=0.4, output_cost_per_1m=1.6),
            "gpt-4.1-nano": ModelPricing(input_cost_per_1m=0.1, output_cost_per_1m=0.4),
            "o1": ModelPricing(input_cost_per_1m=15.0, output_cost_per_1m=60.0),
            "o1-mini": ModelPricing(input_cost_per_1m=1.1, output_cost_per_1m=4.4),
            "o1-pro": ModelPricing(input_cost_per_1m=150.0, output_cost_per_1m=600.0),
            "o3": ModelPricing(input_cost_per_1m=2.0, output_cost_per_1m=8.0),
            "o3-mini": ModelPricing(input_cost_per_1m=1.1, output_cost_per_1m=4.4),
            "o3-pro": ModelPricing(input_cost_per_1m=20.0, output_cost_per_1m=80.0),
            "o3-deep-research": ModelPricing(input_cost_per_1m=10.0, output_cost_per_1m=40.0),
            "o4-mini": ModelPricing(input_cost_per_1m=1.1, output_cost_per_1m=4.4),
        },
        "anthropic": {
            # Claude pricing table from https://docs.anthropic.com/claude/docs/models-overview (retrieved 2025-09-26).
            "claude-opus-4-1": ModelPricing(input_cost_per_1m=15.0, output_cost_per_1m=75.0),
            "claude-sonnet-4": ModelPricing(input_cost_per_1m=3.0, output_cost_per_1m=15.0),
            "claude-3-5-haiku": ModelPricing(input_cost_per_1m=0.80, output_cost_per_1m=4.0),
        },
        "gemini": {
            # Gemini API pricing from https://ai.google.dev/pricing (retrieved 2025-09-26); standard interactive rates.
            "gemini-2.5-pro": ModelPricing(input_cost_per_1m=1.25, output_cost_per_1m=10.0),
            "gemini-2.5-flash": ModelPricing(input_cost_per_1m=0.30, output_cost_per_1m=2.5),
            "gemini-2.5-flash-lite": ModelPricing(input_cost_per_1m=0.10, output_cost_per_1m=0.40),
        },
    }
)


Message = Dict[str, Any]
MessageInput = Union[str, Sequence[Message]]


class BaseLLMProvider:
    """Base functionality all providers inherit from."""

    provider_name: str = "base"
    batch_discount: float = 0.5
    default_max_retries: int = 3
    retry_backoff_seconds: float = 1.5
    retryable_exceptions: Tuple[type[BaseException], ...] = ()

    def __init__(
        self,
        *,
        pricing: ModelPriceRegistry | None = None,
        usage_tracker: LLMUsageTracker | None = None,
        max_retries: Optional[int] = None,
    ) -> None:
        ensure_env_loaded()
        self._pricing = pricing or DEFAULT_PRICING
        self._usage_tracker = usage_tracker or LLMUsageTracker()
        self._max_retries = max_retries or self.default_max_retries

    @property
    def usage_tracker(self) -> LLMUsageTracker:
        return self._usage_tracker

    # Public API -----------------------------------------------------------
    def chat(self, model: str, messages: MessageInput, **kwargs: Any) -> LLMResult:
        message_list = self._prepare_messages(messages)
        return self._execute_with_retry(
            lambda: self._chat_request(model=model, messages=message_list, **kwargs),
            model=model,
            mode="sync",
            metadata=kwargs.get("metadata"),
        )

    def chat_batch(
        self,
        model: str,
        batch_messages: Sequence[MessageInput],
        *,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[LLMResult]:
        results: List[LLMResult] = []
        base_metadata = metadata or {}
        for index, messages in enumerate(batch_messages):
            message_list = self._prepare_messages(messages)
            merged_metadata = {**base_metadata, "batch_index": index}
            result = self._execute_with_retry(
                lambda m=message_list: self._chat_request(model=model, messages=m, **kwargs),
                model=model,
                mode="batch",
                metadata=merged_metadata,
                discount=self.batch_discount,
            )
            results.append(result)
        return results

    async def chat_async(
        self,
        model: str,
        list_of_messages: Sequence[MessageInput],
        *,
        metadata: Optional[Dict[str, Any]] = None,
        concurrency: int = 5,
        **kwargs: Any,
    ) -> List[LLMResult]:
        semaphore = asyncio.Semaphore(concurrency)
        base_metadata = metadata or {}

        async def _run(index: int, messages: MessageInput) -> LLMResult:
            message_list = self._prepare_messages(messages)
            merged_metadata = {**base_metadata, "async_index": index}

            async def _call() -> Any:
                return await self._chat_request_async(model=model, messages=message_list, **kwargs)

            return await self._execute_with_retry_async(
                _call,
                model=model,
                mode="async",
                metadata=merged_metadata,
            )

        tasks = [
            asyncio.create_task(self._with_semaphore(semaphore, _run, idx, messages))
            for idx, messages in enumerate(list_of_messages)
        ]
        return await asyncio.gather(*tasks)

    def read_pdf(
        self,
        model: str,
        pdf_path: Path | str,
        *,
        instructions: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> LLMResult:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        return self._execute_with_retry(
            lambda: self._pdf_request(model=model, pdf_path=pdf_path, instructions=instructions, **kwargs),
            model=model,
            mode="pdf",
            metadata=metadata,
        )

    def read_pdfs(
        self,
        model: str,
        pdf_paths: Sequence[Path | str],
        *,
        instructions: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> LLMResult:
        path_objs: List[Path] = []
        for p in pdf_paths:
            po = Path(p)
            if not po.exists():
                raise FileNotFoundError(f"PDF file not found: {po}")
            path_objs.append(po)
        return self._execute_with_retry(
            lambda: self._pdfs_request(model=model, pdf_paths=tuple(path_objs), instructions=instructions, **kwargs),
            model=model,
            mode="pdf",
            metadata=metadata,
        )

    def read_pdf_batch(
        self,
        model: str,
        pdf_paths: Sequence[Path | str],
        *,
        instructions: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[LLMResult]:
        results: List[LLMResult] = []
        base_metadata = metadata or {}
        for index, pdf_path in enumerate(pdf_paths):
            path_obj = Path(pdf_path)
            if not path_obj.exists():
                raise FileNotFoundError(f"PDF file not found: {path_obj}")
            merged_metadata = {**base_metadata, "batch_index": index}
            result = self._execute_with_retry(
                lambda p=path_obj: self._pdf_request(
                    model=model,
                    pdf_path=p,
                    instructions=instructions,
                    **kwargs,
                ),
                model=model,
                mode="pdf",
                metadata=merged_metadata,
                discount=self.batch_discount,
            )
            results.append(result)
        return results

    # Helper methods -------------------------------------------------------
    def _execute_with_retry(
        self,
        call_factory: Callable[[], Any],
        *,
        model: str,
        mode: str,
        metadata: Optional[Dict[str, Any]],
        discount: float = 1.0,
    ) -> LLMResult:
        attempt = 0
        last_exc: Optional[BaseException] = None
        while attempt < self._max_retries:
            try:
                response = call_factory()
                return self._build_result(
                    response,
                    model=model,
                    mode=mode,
                    metadata=metadata,
                    discount=discount,
                )
            except self.retryable_exceptions as exc:
                last_exc = exc
                sleep_for = self.retry_backoff_seconds * (attempt + 1)
                logger.warning(
                    "Retryable error from %s provider on attempt %s/%s: %s",
                    self.provider_name,
                    attempt + 1,
                    self._max_retries,
                    exc,
                )
                time.sleep(sleep_for)
                attempt += 1
            except Exception as exc:  # pragma: no cover - safety net
                logger.exception("Non-retryable error in provider %s", self.provider_name)
                raise ProviderCallError(str(exc)) from exc
        assert last_exc is not None  # for type checkers
        raise ProviderCallError(f"Provider {self.provider_name} failed after retries: {last_exc}") from last_exc

    async def _execute_with_retry_async(
        self,
        call_factory: Callable[[], Any],
        *,
        model: str,
        mode: str,
        metadata: Optional[Dict[str, Any]],
        discount: float = 1.0,
    ) -> LLMResult:
        attempt = 0
        last_exc: Optional[BaseException] = None
        while attempt < self._max_retries:
            try:
                response = await call_factory()
                return self._build_result(
                    response,
                    model=model,
                    mode=mode,
                    metadata=metadata,
                    discount=discount,
                )
            except self.retryable_exceptions as exc:
                last_exc = exc
                sleep_for = self.retry_backoff_seconds * (attempt + 1)
                logger.warning(
                    "Async retryable error from %s provider on attempt %s/%s: %s",
                    self.provider_name,
                    attempt + 1,
                    self._max_retries,
                    exc,
                )
                await asyncio.sleep(sleep_for)
                attempt += 1
            except Exception as exc:  # pragma: no cover
                logger.exception("Non-retryable async error in provider %s", self.provider_name)
                raise ProviderCallError(str(exc)) from exc
        assert last_exc is not None
        raise ProviderCallError(f"Provider {self.provider_name} failed after retries: {last_exc}") from last_exc

    def _build_result(
        self,
        response: Any,
        *,
        model: str,
        mode: str,
        metadata: Optional[Dict[str, Any]],
        discount: float,
    ) -> LLMResult:
        input_tokens, output_tokens = self._extract_usage(response)
        pricing = self._pricing.get(self.provider_name, model)
        cost = self._calculate_cost(pricing, input_tokens, output_tokens, discount)
        usage = LLMUsage(
            provider=self.provider_name,
            model=model,
            mode=mode,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            metadata=metadata or {},
        )
        self._usage_tracker.add_record(usage)
        content = self._extract_content(response)
        return LLMResult(content=content, usage=usage, raw_response=response)

    def _calculate_cost(
        self,
        pricing: ModelPricing,
        input_tokens: int,
        output_tokens: int,
        discount: float,
    ) -> float:
        million = Decimal(1_000_000)
        input_cost = Decimal(input_tokens) * Decimal(str(pricing.input_cost_per_1m)) / million
        output_cost = Decimal(output_tokens) * Decimal(str(pricing.output_cost_per_1m)) / million
        discounted = (input_cost + output_cost) * Decimal(str(discount))
        quantized = discounted.quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)
        return float(quantized)

    async def _with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        coro_fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        async with semaphore:
            return await coro_fn(*args, **kwargs)

    def _prepare_messages(self, messages: MessageInput) -> List[Message]:
        if isinstance(messages, str):
            return [{"role": "user", "content": messages}]
        prepared: List[Message] = []
        for message in messages:
            if not isinstance(message, dict):
                raise TypeError("Each message must be a dictionary with 'role' and 'content'")
            prepared.append(message)
        return prepared

    # Hooks for subclasses -------------------------------------------------
    def _chat_request(self, *, model: str, messages: Sequence[Message], **kwargs: Any) -> Any:
        raise NotImplementedError

    async def _chat_request_async(self, *, model: str, messages: Sequence[Message], **kwargs: Any) -> Any:
        raise NotImplementedError

    def _pdf_request(
        self,
        *,
        model: str,
        pdf_path: Path,
        instructions: str,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError

    def _pdfs_request(
        self,
        *,
        model: str,
        pdf_paths: Sequence[Path],
        instructions: str,
        **kwargs: Any,
    ) -> Any:
        """Optional: Single request with multiple PDF attachments.

        Subclasses can implement this for providers that support multiple file
        attachments in one call. If not implemented, callers should fall back
        to batching via ``read_pdf_batch``.
        """
        raise NotImplementedError

    def _extract_usage(self, response: Any) -> Tuple[int, int]:
        raise NotImplementedError

    def _extract_content(self, response: Any) -> str:
        raise NotImplementedError


class OpenAIProvider(BaseLLMProvider):
    provider_name = "openai"
    retryable_exceptions = (APITimeoutError, RateLimitError, APIError)
    # Reasoning-oriented families (OpenAI pricing docs, 2025-09) reject
    # temperature controls. Include both canonical IDs and common aliases.
    _REASONING_MODELS = {
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-5-codex",
        "o1",
        "o1-mini",
        "o1-pro",
        "o3",
        "o3-mini",
        "o3-pro",
        "o3-deep-research",
        "o4-mini",
        "o4-mini-deep-research",
    }
    _REASONING_MODEL_PREFIXES = (
        "gpt-5",
        "o1",
        "o3",
        "o4",
    )
    _MODELS_WITHOUT_TEMPERATURE = frozenset(model.lower() for model in _REASONING_MODELS)
    _VALID_REASONING_EFFORTS = frozenset({"low", "medium", "high"})

    def __init__(
        self,
        *,
        client: Optional[OpenAI] = None,
        async_client: Optional[AsyncOpenAI] = None,
        pricing: ModelPriceRegistry | None = None,
        usage_tracker: LLMUsageTracker | None = None,
        max_retries: Optional[int] = None,
    ) -> None:
        super().__init__(pricing=pricing, usage_tracker=usage_tracker, max_retries=max_retries)
        self._client = client or OpenAI()
        self._async_client = async_client or AsyncOpenAI()

    def _chat_request(self, *, model: str, messages: Sequence[Message], **kwargs: Any) -> Any:
        request_kwargs = self._build_chat_kwargs(model, kwargs)
        normalized_messages = self._normalize_messages(messages)
        return self._client.responses.create(
            model=model,
            input=normalized_messages,
            **request_kwargs,
        )

    async def _chat_request_async(self, *, model: str, messages: Sequence[Message], **kwargs: Any) -> Any:
        request_kwargs = self._build_chat_kwargs(model, kwargs)
        normalized_messages = self._normalize_messages(messages)
        return await self._async_client.responses.create(
            model=model,
            input=normalized_messages,
            **request_kwargs,
        )

    def _pdf_request(
        self,
        *,
        model: str,
        pdf_path: Path,
        instructions: str,
        **kwargs: Any,
    ) -> Any:
        request_kwargs = self._build_chat_kwargs(model, kwargs)
        with pdf_path.open("rb") as pdf_file:
            uploaded_file = self._client.files.create(file=pdf_file, purpose="assistants")
        try:
            return self._client.responses.create(
                model=model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": instructions},
                            {"type": "input_file", "file_id": uploaded_file.id},
                        ],
                    }
                ],
                **request_kwargs,
            )
        finally:
            # Best-effort cleanup; ignore errors so the primary response is preserved.
            try:
                self._client.files.delete(uploaded_file.id)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.debug("Failed to delete temporary uploaded file %s", uploaded_file.id)

    def _pdfs_request(
        self,
        *,
        model: str,
        pdf_paths: Sequence[Path],
        instructions: str,
        **kwargs: Any,
    ) -> Any:
        request_kwargs = self._build_chat_kwargs(model, kwargs)
        uploaded_ids: List[str] = []
        try:
            for pdf_path in pdf_paths:
                with pdf_path.open("rb") as f:
                    uploaded = self._client.files.create(file=f, purpose="assistants")
                    uploaded_ids.append(uploaded.id)

            content_blocks: List[Dict[str, Any]] = [{"type": "input_text", "text": instructions}]
            for fid in uploaded_ids:
                content_blocks.append({"type": "input_file", "file_id": fid})

            return self._client.responses.create(
                model=model,
                input=[{"role": "user", "content": content_blocks}],
                **request_kwargs,
            )
        finally:
            for fid in uploaded_ids:
                try:
                    self._client.files.delete(fid)
                except Exception:  # pragma: no cover - best effort
                    logger.debug("Failed to delete temporary uploaded file %s", fid)

    def fallback_read_pdf(
        self,
        *,
        model: str,
        pdf_path: Path | str,
        instructions: str,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LLMResult:
        pdf_path = Path(pdf_path)
        request_kwargs = self._build_chat_kwargs(
            model,
            {
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            },
        )
        with pdf_path.open("rb") as pdf_file:
            uploaded_file = self._client.files.create(file=pdf_file, purpose="assistants")
        try:
            response = self._client.responses.create(
                model=model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": instructions},
                            {"type": "input_file", "file_id": uploaded_file.id},
                        ],
                    }
                ],
                **request_kwargs,
            )
            return self._build_result(
                response,
                model=model,
                mode="pdf",
                metadata=metadata,
                discount=1.0,
            )
        finally:
            try:
                self._client.files.delete(uploaded_file.id)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.debug("Failed to delete temporary uploaded file %s", uploaded_file.id)

    def _build_chat_kwargs(self, model: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        # Allowlist known keyword arguments; ignore unknown ones to reduce risk of API errors.
        allowed_keys = {
            "metadata",
            "temperature",
            "max_output_tokens",
            "max_tokens",
            "response_format",
            "reasoning",
        }
        request_kwargs = {key: value for key, value in kwargs.items() if key in allowed_keys and value is not None}

        reasoning_effort = kwargs.get("reasoning_effort")
        if reasoning_effort is not None:
            if "reasoning" in request_kwargs:
                raise ValueError("Use either 'reasoning' or 'reasoning_effort', not both")
            normalized_effort = str(reasoning_effort).strip().lower()
            if normalized_effort not in self._VALID_REASONING_EFFORTS:
                raise ValueError("reasoning_effort must be one of {'low', 'medium', 'high'}")
            request_kwargs["reasoning"] = {"effort": normalized_effort}

        if "reasoning" in request_kwargs:
            reasoning_payload = request_kwargs["reasoning"]
            if not isinstance(reasoning_payload, dict):
                raise TypeError("OpenAI 'reasoning' payload must be a dictionary")
            normalized_payload = dict(reasoning_payload)
            effort_value = normalized_payload.get("effort")
            if effort_value is not None:
                normalized_effort = str(effort_value).strip().lower()
                if normalized_effort not in self._VALID_REASONING_EFFORTS:
                    raise ValueError("reasoning['effort'] must be one of {'low', 'medium', 'high'}")
                normalized_payload["effort"] = normalized_effort
            request_kwargs["reasoning"] = normalized_payload

        if "temperature" in request_kwargs and self._is_reasoning_model(model):
            logger.debug("Skipping unsupported temperature parameter for reasoning model %s", model)
            request_kwargs.pop("temperature")
        if "max_tokens" in request_kwargs and "max_output_tokens" not in request_kwargs:
            # The Responses API expects max_output_tokens; map legacy arguments so
            # callers migrating from the Completions API keep the same behaviour.
            request_kwargs["max_output_tokens"] = request_kwargs.pop("max_tokens")
        return request_kwargs

    def _is_reasoning_model(self, model: str) -> bool:
        normalized = model.lower()
        if normalized in self._MODELS_WITHOUT_TEMPERATURE:
            return True
        return any(normalized.startswith(prefix) for prefix in self._REASONING_MODEL_PREFIXES)

    def _normalize_messages(self, messages: Sequence[Message]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role is None or content is None:
                raise ValueError("Each message must include 'role' and 'content'")
            if isinstance(content, str):
                normalized.append(
                    {
                        "role": role,
                        "content": [
                            {
                                "type": "input_text",
                                "text": content,
                            }
                        ],
                    }
                )
            elif isinstance(content, list):
                normalized.append({"role": role, "content": content})
            else:
                raise TypeError("Message content must be a string or a list of content blocks")
        return normalized

    def _extract_usage(self, response: Any) -> Tuple[int, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            raise ProviderCallError("OpenAI response missing usage information")
        return int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0)

    def _extract_content(self, response: Any) -> str:
        # New Responses API exposes aggregated text via `output_text` for convenience.
        content = getattr(response, "output_text", None)
        if content:
            return content
        # Fallback to traversing the content array.
        outputs = getattr(response, "output", None)
        if not outputs:
            raise ProviderCallError("OpenAI response missing output content")
        collected: List[str] = []
        for item in outputs:
            parts = getattr(item, "content", []) or []
            for part in parts:
                # Text may be a plain string or an object with `.value`.
                text_value = getattr(part, "text", None)
                if isinstance(text_value, str) and text_value:
                    collected.append(text_value)
                    continue
                if text_value is not None:
                    maybe_val = getattr(text_value, "value", None)
                    if isinstance(maybe_val, str) and maybe_val:
                        collected.append(maybe_val)
                        continue
                # Some SDK variants expose `.type == 'output_text'` and `.content` as str
                part_type = getattr(part, "type", None)
                if part_type in {"output_text", "text"}:
                    maybe_content = getattr(part, "content", None)
                    if isinstance(maybe_content, str) and maybe_content:
                        collected.append(maybe_content)
                if part_type in {"output_file", "file"}:
                    # Attempt to retrieve file content when the model outputs to a file.
                    file_id = getattr(part, "file_id", None)
                    if file_id:
                        try:
                            file_stream = self._client.files.content(file_id)
                            file_bytes = None
                            if hasattr(file_stream, "read"):
                                file_bytes = file_stream.read()
                            elif hasattr(file_stream, "content"):
                                file_bytes = getattr(file_stream, "content")
                            if isinstance(file_bytes, (bytes, bytearray)):
                                try:
                                    collected.append(file_bytes.decode("utf-8", errors="ignore"))
                                except Exception:
                                    # Best effort; ignore undecodable outputs.
                                    pass
                        except Exception:
                            # Some file purposes cannot be downloaded; ignore silently.
                            pass
        if not collected:
            raise ProviderCallError("Unable to extract text from OpenAI response")
        return "\n".join(collected)


class AnthropicProvider(BaseLLMProvider):
    provider_name = "anthropic"

    def _chat_request(self, *, model: str, messages: Sequence[Message], **kwargs: Any) -> Any:  # pragma: no cover
        raise ProviderNotConfiguredError("Anthropic provider not configured. Supply an API client before use.")

    async def _chat_request_async(self, *, model: str, messages: Sequence[Message], **kwargs: Any) -> Any:  # pragma: no cover
        raise ProviderNotConfiguredError("Anthropic provider not configured. Supply an API client before use.")

    def _pdf_request(
        self,
        *,
        model: str,
        pdf_path: Path,
        instructions: str,
        **kwargs: Any,
    ) -> Any:  # pragma: no cover
        raise ProviderNotConfiguredError("Anthropic provider does not yet support PDF workflows in this prototype.")

    def _extract_usage(self, response: Any) -> Tuple[int, int]:  # pragma: no cover - placeholder
        raise ProviderNotConfiguredError("Anthropic provider not configured.")

    def _extract_content(self, response: Any) -> str:  # pragma: no cover - placeholder
        raise ProviderNotConfiguredError("Anthropic provider not configured.")


class GeminiProvider(BaseLLMProvider):
    provider_name = "gemini"

    def _chat_request(self, *, model: str, messages: Sequence[Message], **kwargs: Any) -> Any:  # pragma: no cover
        raise ProviderNotConfiguredError("Gemini provider not configured. Supply an API client before use.")

    async def _chat_request_async(self, *, model: str, messages: Sequence[Message], **kwargs: Any) -> Any:  # pragma: no cover
        raise ProviderNotConfiguredError("Gemini provider not configured. Supply an API client before use.")

    def _pdf_request(
        self,
        *,
        model: str,
        pdf_path: Path,
        instructions: str,
        **kwargs: Any,
    ) -> Any:  # pragma: no cover
        raise ProviderNotConfiguredError("Gemini provider does not yet support PDF workflows in this prototype.")

    def _extract_usage(self, response: Any) -> Tuple[int, int]:  # pragma: no cover - placeholder
        raise ProviderNotConfiguredError("Gemini provider not configured.")

    def _extract_content(self, response: Any) -> str:  # pragma: no cover - placeholder
        raise ProviderNotConfiguredError("Gemini provider not configured.")


class LLMService:
    """High-level orchestrator for interacting with configured providers."""

    def __init__(self, providers: Optional[Dict[str, BaseLLMProvider]] = None) -> None:
        self._providers = providers or {
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
        }

    def get_provider(self, provider_key: str) -> BaseLLMProvider:
        try:
            return self._providers[provider_key]
        except KeyError as exc:
            raise LLMError(f"Unknown provider '{provider_key}'") from exc

    def chat(
        self,
        provider_key: str,
        model: str,
        messages: Sequence[Message],
        *,
        mode: str = "sync",
        **kwargs: Any,
    ) -> LLMResult | List[LLMResult]:
        provider = self.get_provider(provider_key)
        if mode == "sync":
            return provider.chat(model, messages, **kwargs)
        raise ValueError(f"Unsupported mode '{mode}' for single message chat")

    def chat_batch(
        self,
        provider_key: str,
        model: str,
        batch_messages: Sequence[Sequence[Message]],
        **kwargs: Any,
    ) -> List[LLMResult]:
        provider = self.get_provider(provider_key)
        return provider.chat_batch(model, batch_messages, **kwargs)

    async def chat_async(
        self,
        provider_key: str,
        model: str,
        list_of_messages: Sequence[Sequence[Message]],
        **kwargs: Any,
    ) -> List[LLMResult]:
        provider = self.get_provider(provider_key)
        return await provider.chat_async(model, list_of_messages, **kwargs)

    def read_pdf(
        self,
        provider_key: str,
        model: str,
        pdf_path: Path | str,
        *,
        instructions: str,
        **kwargs: Any,
    ) -> LLMResult:
        provider = self.get_provider(provider_key)
        return provider.read_pdf(model, pdf_path, instructions=instructions, **kwargs)

    def read_pdf_batch(
        self,
        provider_key: str,
        model: str,
        pdf_paths: Sequence[Path | str],
        *,
        instructions: str,
        **kwargs: Any,
    ) -> List[LLMResult]:
        provider = self.get_provider(provider_key)
        return provider.read_pdf_batch(model, pdf_paths, instructions=instructions, **kwargs)

    def read_pdfs(
        self,
        provider_key: str,
        model: str,
        pdf_paths: Sequence[Path | str],
        *,
        instructions: str,
        **kwargs: Any,
    ) -> LLMResult:
        provider = self.get_provider(provider_key)
        return provider.read_pdfs(model, pdf_paths, instructions=instructions, **kwargs)

    @property
    def usage_tracker(self) -> LLMUsageTracker:
        tracker = LLMUsageTracker()
        for provider in self._providers.values():
            for record in provider.usage_tracker.records:
                tracker.add_record(record)
        return tracker


__all__ = [
    "AnthropicProvider",
    "BaseLLMProvider",
    "DEFAULT_PRICING",
    "ensure_env_loaded",
    "GeminiProvider",
    "LLMError",
    "LLMResult",
    "LLMService",
    "LLMUsage",
    "LLMUsageTracker",
    "ModelPriceRegistry",
    "ModelPricing",
    "OpenAIProvider",
    "ProviderCallError",
    "ProviderNotConfiguredError",
    "UnknownModelError",
]
