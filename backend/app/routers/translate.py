"""
Implements the full request pipeline from Section 5.3:

  User Input -> Preprocessing -> Base Translation Model -> Validation &
  Correction Layer (<-> Glossary) -> Change-Detection Module (diff log) ->
  Final Output (+ confidence, alternates) -> History & Feedback Store

Every stage records a step in a trace (name, status, duration, summary, details).
The trace is returned to the UI, saved in the diff/audit log, and each step is
also written to the server log as one line (no user text is logged). Each step
also feeds a Prometheus histogram, and Gemini calls feed token-usage counters -
see app/metrics.py and the Grafana dashboard for how these get visualized.
"""
import logging
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.metrics import (
    GEMINI_CALLS,
    GEMINI_TOKENS,
    PIPELINE_STEP_DURATION,
    TRANSLATION_CONFIDENCE,
    TRANSLATION_REQUESTS,
    TRANSLATIONS_IN_PROGRESS,
    VALIDATION_FALLBACKS,
)
from app.models import DiffLog, Translation, User
from app.pipeline import preprocessing
from app.pipeline.base_model import get_base_model
from app.pipeline.diff_utils import compute_word_diff
from app.pipeline.errors import QuotaExceededError
from app.pipeline.glossary_store import find_relevant_terms, format_glossary_for_prompt
from app.pipeline.validation import ValidationError, ValidationTimeout, get_validation_layer
from app.schemas import TranslateRequest, TranslateResponse

logger = logging.getLogger("translation.pipeline")

router = APIRouter(prefix="/translate", tags=["translate"])

# Mirrors the threshold used inside preprocessing.detect_language (shown in the trace only).
ROMAN_URDU_THRESHOLD = 0.15


class PipelineTrace:
    """Collects one entry per pipeline stage and records its duration to Prometheus."""

    def __init__(self):
        self.request_id = uuid.uuid4().hex[:8]
        self.steps: List[dict] = []
        self._started = time.perf_counter()

    def add(self, name: str, status: str, step_started: float, summary: str, details: Optional[dict] = None):
        duration_s = time.perf_counter() - step_started
        duration_ms = int(duration_s * 1000)
        step_no = len(self.steps) + 1
        self.steps.append(
            {
                "step": step_no,
                "name": name,
                "status": status,
                "duration_ms": duration_ms,
                "summary": summary,
                "details": details or {},
            }
        )
        logger.info("[req %s] step %d | %s | %s | %d ms | %s", self.request_id, step_no, name, status, duration_ms, summary)
        PIPELINE_STEP_DURATION.labels(step_name=name).observe(duration_s)

    def total_ms(self) -> int:
        return int((time.perf_counter() - self._started) * 1000)


def quota_http_error(exc: QuotaExceededError) -> HTTPException:
    """Turn a Gemini quota error into a readable HTTP 429 for the frontend."""
    if exc.daily:
        detail = (
            "The Gemini API daily quota for the translation model is used up. It resets at "
            "midnight Pacific time. Switch GEMINI_MODEL in .env to another model, use a key "
            "from a new Google AI Studio project, or enable billing."
        )
    else:
        wait = f" Try again in about {int(exc.retry_after) + 1}s." if exc.retry_after else ""
        detail = f"Gemini API rate limit hit (too many requests per minute).{wait}"

    headers = {"Retry-After": str(int(exc.retry_after) + 1)} if exc.retry_after else None
    return HTTPException(status_code=429, detail=detail, headers=headers)


def _record_gemini_tokens(user_email: str, role: str, prompt_tokens: int, completion_tokens: int):
    if prompt_tokens:
        GEMINI_TOKENS.labels(user_email=user_email, role=role, token_type="prompt").inc(prompt_tokens)
    if completion_tokens:
        GEMINI_TOKENS.labels(user_email=user_email, role=role, token_type="completion").inc(completion_tokens)


@router.post("", response_model=TranslateResponse)
async def translate(
    payload: TranslateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not payload.text.strip():
        # TC-08: empty input must not reach the base model
        raise HTTPException(status_code=422, detail="Please enter text to translate")

    trace = PipelineTrace()
    clean_text = payload.text.strip()
    TRANSLATIONS_IN_PROGRESS.inc()

    try:
        # --- Step 1: Input received ---
        t = time.perf_counter()
        trace.add(
            "Input received",
            "ok",
            t,
            f"{len(clean_text)} characters received",
            {
                "text": clean_text,
                "requested_source_lang": payload.source_lang,
                "requested_target_lang": payload.target_lang or "(default for the detected direction)",
            },
        )

        # --- Step 2: Language detection (FR-08) ---
        t = time.perf_counter()
        if payload.source_lang == "auto":
            source_lang = preprocessing.detect_language(clean_text)
            tokens = preprocessing._tokenize(clean_text)
            marker_hits = [tok for tok in tokens if tok in preprocessing.ROMAN_URDU_MARKERS]
            ratio = (len(marker_hits) / len(tokens)) if tokens else 0.0
            detection_details = {
                "method": "rule-based: Urdu script check, then Roman Urdu marker-word ratio",
                "urdu_script_found": bool(preprocessing.URDU_SCRIPT_RE.search(clean_text)),
                "roman_urdu_marker_words_found": marker_hits,
                "marker_ratio": round(ratio, 3),
                "roman_urdu_threshold": ROMAN_URDU_THRESHOLD,
            }
        else:
            source_lang = payload.source_lang
            detection_details = {"method": "language selected by the user (auto-detect skipped)"}

        target_lang = payload.target_lang or preprocessing.default_target_for(source_lang)
        detection_details["source_lang"] = source_lang
        detection_details["target_lang"] = target_lang
        detection_details["target_chosen_by"] = "user override" if payload.target_lang else "default for this direction"
        trace.add(
            "Language detection",
            "ok" if payload.source_lang == "auto" else "skipped",
            t,
            f"{source_lang} -> {target_lang}",
            detection_details,
        )

        # --- Step 3: Normalization, typo and short-form correction (FR-05, FR-06) ---
        t = time.perf_counter()
        normalized_text, pre_corrections = preprocessing.normalize_and_correct(clean_text, source_lang)
        trace.add(
            "Normalization & correction",
            "ok",
            t,
            f"{len(pre_corrections)} correction(s) applied" if pre_corrections else "No changes needed",
            {
                "input_text": clean_text,
                "normalized_text": normalized_text,
                "text_changed": normalized_text != clean_text,
                "corrections": pre_corrections,
            },
        )

        # --- Step 4: Base translation model (raw output) ---
        t = time.perf_counter()
        base_model = get_base_model()
        try:
            base_result = await base_model.translate(normalized_text, source_lang, target_lang)
        except QuotaExceededError as exc:
            GEMINI_CALLS.labels(role="base_translation", status="error").inc()
            trace.add("Base translation", "failed", t, "Gemini quota exceeded", {"error": str(exc)[:300]})
            TRANSLATION_REQUESTS.labels(source_lang=source_lang, target_lang=target_lang, status="error").inc()
            raise quota_http_error(exc) from exc
        except Exception as exc:  # noqa: BLE001
            GEMINI_CALLS.labels(role="base_translation", status="error").inc()
            trace.add("Base translation", "failed", t, f"{type(exc).__name__}", {"error": str(exc)[:300]})
            logger.exception("Base translation model failed")
            TRANSLATION_REQUESTS.labels(source_lang=source_lang, target_lang=target_lang, status="error").inc()
            raise HTTPException(status_code=502, detail=f"Base translation model failed: {exc}") from exc

        raw_output = base_result.text
        GEMINI_CALLS.labels(role="base_translation", status="ok").inc()
        _record_gemini_tokens(user.email, "base_translation", base_result.prompt_tokens, base_result.completion_tokens)
        trace.add(
            "Base translation",
            "ok",
            t,
            f"Raw translation produced ({len(raw_output)} characters, {base_result.total_tokens} tokens)",
            {
                "model": settings.GEMINI_MODEL,
                "input_text": normalized_text,
                "raw_output": raw_output,
                "prompt_tokens": base_result.prompt_tokens,
                "completion_tokens": base_result.completion_tokens,
                "total_tokens": base_result.total_tokens,
            },
        )

        # --- Step 5: Glossary lookup (FR-09) ---
        t = time.perf_counter()
        glossary_terms = find_relevant_terms(db, normalized_text)
        glossary_context = format_glossary_for_prompt(glossary_terms)
        trace.add(
            "Glossary lookup",
            "ok",
            t,
            f"{len(glossary_terms)} glossary term(s) matched" if glossary_terms else "No glossary terms matched",
            {
                "matched_terms": [
                    {"term": g.term, "domain": g.domain, "canonical_translation": g.canonical_translation}
                    for g in glossary_terms
                ],
                "context_sent_to_validator": glossary_context,
            },
        )

        # --- Step 6: Validation & correction layer ---
        t = time.perf_counter()
        is_validated = True
        correction_reasons = list(pre_corrections)  # typo/short-form fixes count as corrections too
        try:
            validation_layer = get_validation_layer()
            result = await validation_layer.validate(
                source_text=normalized_text,
                raw_translation=raw_output,
                source_lang=source_lang,
                target_lang=target_lang,
                glossary_context=glossary_context,
            )
            validated_output = result.validated_output
            confidence = result.confidence
            alternates = result.alternates
            correction_reasons += result.correction_reasons
            GEMINI_CALLS.labels(role="validation", status="ok").inc()
            _record_gemini_tokens(user.email, "validation", result.prompt_tokens, result.completion_tokens)
            TRANSLATION_CONFIDENCE.observe(confidence)
            trace.add(
                "Validation & correction",
                "ok",
                t,
                f"Confidence {round(confidence * 100)}%, {len(result.correction_reasons)} correction reason(s) from validator",
                {
                    "model": settings.GEMINI_MODEL,
                    "timeout_seconds": settings.VALIDATION_TIMEOUT_SECONDS,
                    "validated_output": validated_output,
                    "confidence": confidence,
                    "alternates": alternates,
                    "correction_reasons_from_validator": result.correction_reasons,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "total_tokens": result.total_tokens,
                },
            )
        except (ValidationTimeout, ValidationError) as exc:
            # NFR-04 / UC-09: fail gracefully to the raw base-model output.
            GEMINI_CALLS.labels(role="validation", status="error").inc()
            VALIDATION_FALLBACKS.inc()
            logger.warning("[req %s] validation failed, serving raw output: %s", trace.request_id, exc)
            validated_output = raw_output
            confidence = None
            alternates = []
            is_validated = False
            correction_reasons.append(f"validation_unavailable: {str(exc)[:200]}")
            trace.add(
                "Validation & correction",
                "fallback",
                t,
                "Validation failed, raw output served instead",
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                    "served": "raw base-model output (UC-09 / NFR-04 fallback)",
                },
            )

        # --- Step 7: Change detection (diff raw vs validated) ---
        t = time.perf_counter()
        diff_ops = compute_word_diff(raw_output, validated_output)
        trace.add(
            "Change detection",
            "ok",
            t,
            f"{len(diff_ops)} change(s) between raw and validated output"
            if diff_ops
            else "No differences between raw and validated output",
            {"changes": diff_ops, "output_changed": bool(diff_ops)},
        )

        # --- Step 8: Persist to History DB + Diff/Audit Log ---
        t = time.perf_counter()
        translation = Translation(
            user_id=user.id,
            source_text=payload.text,
            source_lang=source_lang,
            target_lang=target_lang,
            raw_output=raw_output,
            validated_output=validated_output,
            final_output=validated_output,
            confidence=confidence,
            alternates=alternates,
            is_validated=is_validated,
        )
        db.add(translation)
        db.flush()  # get translation.id before commit
        trace.add(
            "Saved to history & audit log",
            "ok",
            t,
            "Translation, diff and this trace stored",
            {"translation_id": translation.id},
        )

        diff_log = DiffLog(
            translation_id=translation.id,
            raw_output=raw_output,
            validated_output=validated_output,
            diff=diff_ops,
            correction_reason=correction_reasons,
            confidence_before=None,
            confidence_after=confidence,
            trace=trace.steps,
        )
        db.add(diff_log)
        db.commit()
        db.refresh(translation)

        TRANSLATION_REQUESTS.labels(
            source_lang=source_lang,
            target_lang=target_lang,
            status="ok" if is_validated else "fallback",
        ).inc()

        return TranslateResponse(
            id=translation.id,
            source_text=translation.source_text,
            source_lang=translation.source_lang,
            target_lang=translation.target_lang,
            raw_output=translation.raw_output,
            validated_output=translation.validated_output,
            final_output=translation.final_output,
            confidence=translation.confidence,
            alternates=translation.alternates,
            is_validated=translation.is_validated,
            diff=diff_ops,
            correction_reason=correction_reasons,
            trace=trace.steps,
            total_ms=trace.total_ms(),
            timestamp=translation.timestamp,
        )
    finally:
        TRANSLATIONS_IN_PROGRESS.dec()