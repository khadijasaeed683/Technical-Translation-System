from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Feedback, Translation, User
from app.schemas import FeedbackCreate, FeedbackOut

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=201)
def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    translation = (
        db.query(Translation)
        .filter(Translation.id == payload.translation_id, Translation.user_id == user.id)
        .first()
    )
    if not translation:
        raise HTTPException(status_code=404, detail="Translation not found")

    existing = db.query(Feedback).filter(Feedback.translation_id == payload.translation_id).first()
    if existing:
        existing.rating = payload.rating
        existing.comment = payload.comment
        db.commit()
        db.refresh(existing)
        return existing

    feedback = Feedback(
        translation_id=payload.translation_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback
