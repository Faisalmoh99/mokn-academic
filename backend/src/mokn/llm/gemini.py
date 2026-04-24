"""Single source of truth for Gemini calls.

All agents talk to the LLM through `GeminiClient.generate()`. This keeps
prompt/response logging, retry, temperature defaults, and structured output
handling in one place — and lets us swap models later without touching agents.

Uses the current `google-genai` SDK (the `google.generativeai` package was
deprecated in 2025).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, TypeVar, overload

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mokn.config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiError(RuntimeError):
    """Wraps any failure from the Gemini SDK after retries are exhausted."""


class GeminiClient:
    """Thin async wrapper around `google-genai` with structured output.

    - `temperature` defaults to 0.3 — agents need consistency, not creativity.
    - If `response_schema` is given, returns a validated Pydantic instance.
    - Otherwise returns raw text.
    - Prompt+response are JSONL-logged per call for debugging.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = genai.Client(api_key=self._settings.gemini_api_key)
        self._log_dir = self._settings.llm_log_path
        self._log_dir.mkdir(parents=True, exist_ok=True)

    @overload
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = ...,
        temperature: float = ...,
        response_schema: type[T],
        model: str | None = ...,
    ) -> T: ...

    @overload
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = ...,
        temperature: float = ...,
        response_schema: None = ...,
        model: str | None = ...,
    ) -> str: ...

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.3,
        response_schema: type[T] | None = None,
        model: str | None = None,
    ) -> str | T:
        model_name = model or self._settings.default_model_name
        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if system is not None:
            config_kwargs["system_instruction"] = system
        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            raw_schema = response_schema.model_json_schema()
            config_kwargs["response_schema"] = _sanitize_schema_for_gemini(raw_schema)

        config = genai_types.GenerateContentConfig(**config_kwargs)
        call_id = uuid.uuid4().hex[:12]

        try:
            raw_text = await self._call_with_retry(model_name, prompt, config, call_id)
        except RetryError as exc:
            raise GeminiError(f"Gemini call {call_id} failed after retries") from exc

        if response_schema is None:
            return raw_text

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise GeminiError(
                f"Gemini returned non-JSON for schema {response_schema.__name__}: {raw_text[:200]}"
            ) from exc
        return response_schema.model_validate(payload)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=False,
    )
    async def _call_with_retry(
        self,
        model_name: str,
        prompt: str,
        config: genai_types.GenerateContentConfig,
        call_id: str,
    ) -> str:
        response = await self._client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        text = _extract_text(response)
        self._log_call(call_id, prompt, text)
        return text

    def _log_call(self, call_id: str, prompt: str, response_text: str) -> None:
        try:
            entry = {
                "call_id": call_id,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "prompt": prompt,
                "response": response_text,
            }
            day_file = self._log_dir / f"{datetime.now(tz=timezone.utc):%Y-%m-%d}.jsonl"
            with day_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            logger.warning("Failed to persist LLM call log", exc_info=True)


def _sanitize_schema_for_gemini(schema: Any) -> Any:
    """Recursively strip JSON-Schema fields Gemini's structured output rejects.

    Pydantic v2 emits ``additionalProperties`` on object schemas (including
    nested models and ``dict[str, X]`` mappings). Gemini's ``response_schema``
    validator does not accept that field and raises ``ValueError``. We walk the
    schema, drop the key everywhere it appears, and return a plain dict that
    the SDK will pass through unchanged.

    Add further incompatibilities here if they surface.
    """
    if isinstance(schema, dict):
        cleaned: dict[str, Any] = {}
        for key, value in schema.items():
            if key == "additionalProperties":
                continue
            cleaned[key] = _sanitize_schema_for_gemini(value)
        return cleaned
    if isinstance(schema, list):
        return [_sanitize_schema_for_gemini(item) for item in schema]
    return schema


def _extract_text(response: Any) -> str:
    """Best-effort text extraction across google-genai response shapes."""
    text = getattr(response, "text", None)
    if isinstance(text, str) and text:
        return text
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        parts = getattr(getattr(cand, "content", None), "parts", None) or []
        for part in parts:
            inner = getattr(part, "text", None)
            if isinstance(inner, str) and inner:
                return inner
    raise GeminiError("Empty response from Gemini")


@lru_cache(maxsize=1)
def get_gemini_client() -> GeminiClient:
    return GeminiClient()


def _reset_client_cache_for_tests() -> None:  # pragma: no cover
    """Escape hatch for tests that need to reconfigure the client."""
    get_gemini_client.cache_clear()
