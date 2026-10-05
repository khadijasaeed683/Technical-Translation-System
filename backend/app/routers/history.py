from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Translation, User
from app.schemas import HistoryItem, TraceResponse

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=List[HistoryItem])
def get_history(
    keyword: Optional[str] = Query(default=None, description="Search source or validated text"),
    source_lang: Optional[str] = Query(default=None),
    target_lang: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Translation).filter(Translation.user_id == user.id)

    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            (Translation.source_text.ilike(like)) | (Translation.validated_output.ilike(like))
        )
    if source_lang:
        q = q.filter(Translation.source_lang == source_lang)
    if target_lang:
        q = q.filter(Translation.target_lang == target_lang)
    if date_from:
        q = q.filter(Translation.timestamp >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.filter(Translation.timestamp <= datetime.combine(date_to, datetime.max.time()))

    return q.order_by(Translation.timestamp.desc()).limit(200).all()


@router.get("/{translation_id}/trace", response_model=TraceResponse)
def get_trace(translation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Step-by-step pipeline log for one past translation. Empty for translations made before tracing existed."""
    translation = (
        db.query(Translation)
        .filter(Translation.id == translation_id, Translation.user_id == user.id)
        .first()
    )
    if not translation:
        raise HTTPException(status_code=404, detail="Translation not found")

    steps = translation.diff_log.trace if translation.diff_log and translation.diff_log.trace else []
    return TraceResponse(id=translation.id, trace=steps)


@router.delete("/{translation_id}", status_code=204)
def delete_history_item(translation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """NFR-05: users can delete their history."""
    db.query(Translation).filter(
        Translation.id == translation_id, Translation.user_id == user.id
    ).delete()
    db.commit()
    return None
