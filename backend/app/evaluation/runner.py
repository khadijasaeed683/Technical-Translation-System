"""
Section 7.1 methodology: for every sentence in the evaluation set, compare
three outputs against the human reference:
  Baseline A: commercial MT baseline (Google Translate, falling back to
              MyMemory if Google is unreachable/blocked from this environment)
  Baseline B: raw base-model (Gemini) output, unvalidated
  Our System: base-model output after the validation & correction layer

Notes:
  - The base model is called ONCE per sentence, not twice. "Our system"
    reuses the same raw translation used for Baseline B and only adds the
    validation call on top.
  - Baseline A tries Google Translate, then falls back to MyMemory if Google
    fails (free/unofficial Google Translate access is commonly IP-blocked
    when called from a server or Docker container).
  - A short delay between sentences avoids tripping Gemini's per-minute limit.
  - Gemini token usage from both calls is recorded to Prometheus labeled
    user_email="evaluation" (there's no end-user for a batch eval run),
    so an evaluation run's cost is visible in Grafana like any other usage.
  - Failure counts for every system are attached to the stored metrics under
    "_meta" so a 0.0 caused by failed calls is distinguishable from a 0.0
    caused by genuinely bad translations.
"""
import asyncio
import logging
from typing import List, Optional, Tuple

from deep_translator import GoogleTranslator, MyMemoryTranslator
from sqlalchemy.orm import Session

from app.config import settings
from app.evaluation.dataset import EvalSentencePair, load_eval_dataset
from app.evaluation.metrics import build_metrics_table
from app.metrics import GEMINI_CALLS, GEMINI_TOKENS, TRANSLATION_CONFIDENCE, VALIDATION_FALLBACKS
from app.models import EvaluationRun
from app.pipeline.base_model import get_base_model
from app.pipeline.glossary_store import find_relevant_terms, format_glossary_for_prompt
from app.pipeline.validation import ValidationError, ValidationTimeout, get_validation_layer

logger = logging.getLogger("translation.evaluation")

_GT_LANG_MAP = {"en": "en", "ur": "ur", "ur-roman": "ur"}  # Google Translate has no Roman Urdu mode
_MM_LANG_MAP = {"en": "en-GB", "ur": "ur-PK", "ur-roman": "ur-PK"}  # MyMemory wants locale-style codes

_CALL_DELAY = getattr(settings, "EVAL_CALL_DELAY_SECONDS", 3.0)
_EVAL_USER_LABEL = "evaluation"  # fixed label: a batch eval run has no single end-user


def _translate_with_mymemory(pair: EvalSentencePair) -> str:
    src = _MM_LANG_MAP.get(pair.source_lang, "en-GB")
    tgt = _MM_LANG_MAP.get(pair.target_lang, "en-GB")
    return MyMemoryTranslator(source=src, target=tgt).translate(pair.source_text) or ""


def _baseline_a_one(pair: EvalSentencePair) -> Tuple[str, bool, str]:
    """
    Returns (output, ok, provider). Tries Google Translate first; if that
    fails (commonly IP-blocked from a server/container), falls back to
    MyMemory before giving up.
    """
    try:
        src = _GT_LANG_MAP.get(pair.source_lang, "auto")
        tgt = _GT_LANG_MAP.get(pair.target_lang, "en")
        result = GoogleTranslator(source=src, target=tgt).translate(pair.source_text)
        if result:
            return result, True, "google"
        logger.warning("Google Translate returned empty output for sentence %s", pair.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Translate failed for sentence %s: %s", pair.id, exc)

    try:
        result = _translate_with_mymemory(pair)
        if result:
            return result, True, "mymemory"
        logger.warning("MyMemory also returned empty output for sentence %s", pair.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MyMemory also failed for sentence %s: %s", pair.id, exc)

    return "", False, "none"


async def _validate_one(db: Session, pair: EvalSentencePair, raw: str) -> Tuple[str, bool]:
    """Runs the validation layer on an ALREADY-TRANSLATED raw output. Returns (output, was_validated)."""
    terms = find_relevant_terms(db, pair.source_text)
    context = format_glossary_for_prompt(terms)
    try:
        result = await get_validation_layer().validate(
            source_text=pair.source_text,
            raw_translation=raw,
            source_lang=pair.source_lang,
            target_lang=pair.target_lang,
            glossary_context=context,
        )
        GEMINI_CALLS.labels(role="evaluation_validation", status="ok").inc()
        if result.prompt_tokens:
            GEMINI_TOKENS.labels(user_email=_EVAL_USER_LABEL, role="validation", token_type="prompt").inc(result.prompt_tokens)
        if result.completion_tokens:
            GEMINI_TOKENS.labels(user_email=_EVAL_USER_LABEL, role="validation", token_type="completion").inc(result.completion_tokens)
        TRANSLATION_CONFIDENCE.observe(result.confidence)
        return result.validated_output, True
    except (ValidationTimeout, ValidationError) as exc:
        GEMINI_CALLS.labels(role="evaluation_validation", status="error").inc()
        VALIDATION_FALLBACKS.inc()
        logger.warning("Validation failed for sentence %s, falling back to raw output: %s", pair.id, exc)
        return raw, False


async def run_evaluation(db: Session, sample_size: Optional[int], triggered_by: Optional[str]) -> EvaluationRun:
    pairs = load_eval_dataset(sample_size)
    base_model = get_base_model()

    references: List[str] = [p.human_reference for p in pairs]
    sources: List[str] = [p.source_text for p in pairs]

    google_hyp: List[str] = []
    raw_base_hyp: List[str] = []
    our_system_hyp: List[str] = []

    baseline_a_failures = 0
    google_used = 0
    mymemory_used = 0
    base_model_failures = 0
    validation_failures = 0

    for i, p in enumerate(pairs):
        gt_text, gt_ok, provider = _baseline_a_one(p)
        google_hyp.append(gt_text)
        if not gt_ok:
            baseline_a_failures += 1
        elif provider == "google":
            google_used += 1
        elif provider == "mymemory":
            mymemory_used += 1

        try:
            base_result = await base_model.translate(p.source_text, p.source_lang, p.target_lang)
            raw = base_result.text
            GEMINI_CALLS.labels(role="evaluation_base", status="ok").inc()
            if base_result.prompt_tokens:
                GEMINI_TOKENS.labels(user_email=_EVAL_USER_LABEL, role="base_translation", token_type="prompt").inc(base_result.prompt_tokens)
            if base_result.completion_tokens:
                GEMINI_TOKENS.labels(user_email=_EVAL_USER_LABEL, role="base_translation", token_type="completion").inc(base_result.completion_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Base model failed for sentence %s: %s", p.id, exc)
            GEMINI_CALLS.labels(role="evaluation_base", status="error").inc()
            raw = ""
            base_model_failures += 1
        raw_base_hyp.append(raw)

        # Reuse `raw` instead of translating the sentence a second time.
        if raw:
            output, validated_ok = await _validate_one(db, p, raw)
            if not validated_ok:
                validation_failures += 1
        else:
            output = ""
        our_system_hyp.append(output)

        if i < len(pairs) - 1 and _CALL_DELAY > 0:
            await asyncio.sleep(_CALL_DELAY)  # stay under per-minute rate limits

    metrics = build_metrics_table(references, sources, google_hyp, raw_base_hyp, our_system_hyp)
    metrics["_meta"] = {
        "dataset_size": len(pairs),
        "baseline_a_failures": baseline_a_failures,
        "baseline_a_via_google": google_used,
        "baseline_a_via_mymemory": mymemory_used,
        "base_model_failures": base_model_failures,
        "validation_failures": validation_failures,
    }
    if baseline_a_failures == len(pairs):
        logger.warning(
            "Both Google Translate and the MyMemory fallback failed for every sentence "
            "(%d/%d) - its BLEU/chrF++ of 0.0 reflects failed calls, not translation "
            "quality. Likely no outbound internet access to these services from this "
            "environment/container.",
            baseline_a_failures, len(pairs),
        )
    elif google_used == 0 and mymemory_used > 0:
        logger.info(
            "Google Translate was unreachable for every sentence; all %d Baseline A "
            "results came from the MyMemory fallback instead.", mymemory_used,
        )
    if base_model_failures + validation_failures >= len(pairs):
        logger.warning(
            "Nearly every base-model or validation call failed (%d base, %d validation, "
            "out of %d sentences) - check for a Gemini quota error in the logs above.",
            base_model_failures, validation_failures, len(pairs),
        )

    per_sentence = [
        {
            "id": p.id,
            "source_text": p.source_text,
            "domain": p.domain,
            "human_reference": p.human_reference,
            "google_translate": google_hyp[i],
            "raw_base_model": raw_base_hyp[i],
            "our_system": our_system_hyp[i],
        }
        for i, p in enumerate(pairs)
    ]

    run = EvaluationRun(
        triggered_by=triggered_by,
        dataset_size=len(pairs),
        metrics=metrics,
        per_sentence_results=per_sentence,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
