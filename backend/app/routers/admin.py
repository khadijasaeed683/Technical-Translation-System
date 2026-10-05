from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import DiffLog, Feedback, Translation, User
from app.schemas import AdminAnalytics

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/analytics", response_model=AdminAnalytics)
def analytics(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    total_translations = db.query(Translation).count()
    feedback_rows = db.query(Feedback).all()
    total_feedback = len(feedback_rows)
    thumbs_up = sum(1 for f in feedback_rows if f.rating == "up")
    thumbs_down = sum(1 for f in feedback_rows if f.rating == "down")
    thumbs_up_rate = (thumbs_up / total_feedback) if total_feedback else 0.0

    diff_rows = db.query(DiffLog).all()
    corrected = sum(1 for d in diff_rows if d.diff)
    correction_rate = (corrected / len(diff_rows)) if diff_rows else 0.0

    unvalidated = db.query(Translation).filter(Translation.is_validated == False).count()  # noqa: E712
    unvalidated_fallback_rate = (unvalidated / total_translations) if total_translations else 0.0

    reason_counter = Counter()
    for d in diff_rows:
        for reason in d.correction_reason or []:
            # normalize "typo_fix: 'sen' -> 'send'" down to its category prefix
            category = reason.split(":")[0].strip()
            reason_counter[category] += 1
    top_reasons = [{"reason": r, "count": c} for r, c in reason_counter.most_common(10)]

    return AdminAnalytics(
        total_translations=total_translations,
        total_feedback=total_feedback,
        thumbs_up=thumbs_up,
        thumbs_down=thumbs_down,
        thumbs_up_rate=round(thumbs_up_rate, 4),
        correction_rate=round(correction_rate, 4),
        unvalidated_fallback_rate=round(unvalidated_fallback_rate, 4),
        top_correction_reasons=top_reasons,
    )
