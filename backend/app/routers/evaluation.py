from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_admin
from app.evaluation.runner import run_evaluation
from app.models import EvaluationRun, User
from app.pipeline.errors import QuotaExceededError
from app.routers.translate import quota_http_error
from app.schemas import EvaluationMetricRow, EvaluationResult, EvaluationTriggerRequest

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

_METRIC_LABELS = {
    "bleu_overall": "BLEU (overall)",
    "chrf_overall": "chrF++ (overall)",
    "terminology_accuracy_jargon_subset": "Terminology accuracy (jargon subset)",
}


def _to_result(run: EvaluationRun) -> EvaluationResult:
    rows = []
    for key, label in _METRIC_LABELS.items():
        m = run.metrics.get(key, {})
        rows.append(
            EvaluationMetricRow(
                metric=label,
                google_translate=m.get("google_translate"),
                raw_base_model=m.get("raw_base_model"),
                our_system=m.get("our_system"),
            )
        )
    return EvaluationResult(id=run.id, dataset_size=run.dataset_size, metrics=rows, timestamp=run.timestamp)


@router.post("/run", response_model=EvaluationResult)
async def trigger_evaluation(
    payload: EvaluationTriggerRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Runs the Section 7.1 comparison (Google Translate vs raw base model vs
    our validated system) against the evaluation dataset and stores the
    result. Costs ~2 Gemini calls per sentence, so on a free-tier key set
    EVAL_DEFAULT_SAMPLE_SIZE in .env (or pass sample_size here).
    """
    sample_size = payload.sample_size or settings.EVAL_DEFAULT_SAMPLE_SIZE or None
    try:
        run = await run_evaluation(db, sample_size, triggered_by=admin.id)
    except QuotaExceededError as exc:
        raise quota_http_error(exc) from exc
    return _to_result(run)


@router.get("/results", response_model=List[EvaluationResult])
def list_results(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    runs = db.query(EvaluationRun).order_by(EvaluationRun.timestamp.desc()).limit(20).all()
    return [_to_result(r) for r in runs]


@router.get("/results/latest", response_model=EvaluationResult)
def latest_result(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    run = db.query(EvaluationRun).order_by(EvaluationRun.timestamp.desc()).first()
    if run is None:
        raise HTTPException(status_code=404, detail="No evaluation runs yet")
    return _to_result(run)
