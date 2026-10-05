"""
Base Translation Model (Table 5.1, row 4) — "Third-party MT/LLM API
(pluggable — e.g., a GPT-class model, NLLB, or a commercial MT API) that
produces the initial raw translation."

NFR-07 requires this to be swappable without rewriting the validation layer,
so every implementation goes through the BaseTranslationModel interface.
Only GeminiBaseModel is wired up by default; add another subclass and change
get_base_model() to swap it.

translate() returns a TranslationOutput (text + token counts) rather than a
bare string, so callers can record Gemini token usage (for the Grafana
"tokens used" panels) without a second, separate call.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import google.generativeai as genai

from app.config import settings
from app.pipeline.errors import as_quota_error

LANG_NAMES = {"en": "English", "ur": "Urdu", "ur-roman": "Roman Urdu (Urdu written in Latin script)"}


@dataclass
class TranslationOutput:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class BaseTranslationModel(ABC):
    @abstractmethod
    async def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationOutput:
        """Return a raw translation with no glossary/validation applied."""
        raise NotImplementedError


def _extract_usage(response) -> tuple[int, int, int]:
    """
    Reads token counts off a Gemini response. Guarded with getattr because
    usage_metadata has been missing/None on some SDK versions and some error
    responses - metrics should degrade to 0 silently, never crash a translation.
    """
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return 0, 0, 0
    prompt = getattr(usage, "prompt_token_count", 0) or 0
    completion = getattr(usage, "candidates_token_count", 0) or 0
    total = getattr(usage, "total_token_count", 0) or (prompt + completion)
    return prompt, completion, total


class GeminiBaseModel(BaseTranslationModel):
    """
    Uses Gemini as the raw/base translator (Baseline B in Section 7.1).
    Deliberately a plain, un-glossaried prompt — this output is meant to
    represent what a general-purpose model produces on its own, so the
    validation layer's improvement over it is measurable (Section 6, 7, 10.2).
    """

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationOutput:
        src = LANG_NAMES.get(source_lang, source_lang)
        tgt = LANG_NAMES.get(target_lang, target_lang)
        prompt = (
            f"Translate the following {src} text into {tgt}. "
            f"Return ONLY the translated text, with no explanation, no quotes, "
            f"and no preamble.\n\nText: {text}"
        )
        try:
            response = await self.model.generate_content_async(prompt)
        except Exception as exc:  # noqa: BLE001
            quota_error = as_quota_error(exc)
            if quota_error:
                raise quota_error from exc  # callers turn this into a clear HTTP 429
            raise
        prompt_tok, completion_tok, total_tok = _extract_usage(response)
        return TranslationOutput(
            text=(response.text or "").strip(),
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
            total_tokens=total_tok,
        )


_base_model_instance: Optional[BaseTranslationModel] = None


def get_base_model() -> BaseTranslationModel:
    global _base_model_instance
    if _base_model_instance is None:
        _base_model_instance = GeminiBaseModel()
    return _base_model_instance