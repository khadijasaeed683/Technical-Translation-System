from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin, get_current_user
from app.models import GlossaryTerm, User
from app.schemas import GlossaryTermCreate, GlossaryTermOut

router = APIRouter(prefix="/glossary", tags=["glossary"])


@router.get("", response_model=List[GlossaryTermOut])
def list_terms(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(GlossaryTerm).order_by(GlossaryTerm.domain, GlossaryTerm.term).all()


@router.post("", response_model=GlossaryTermOut, status_code=201)
def create_term(
    payload: GlossaryTermCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)
):
    term = GlossaryTerm(**payload.model_dump())
    db.add(term)
    db.commit()
    db.refresh(term)
    return term


@router.put("/{term_id}", response_model=GlossaryTermOut)
def update_term(
    term_id: str,
    payload: GlossaryTermCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    term = db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Glossary term not found")
    for field, value in payload.model_dump().items():
        setattr(term, field, value)
    db.commit()
    db.refresh(term)
    return term


@router.delete("/{term_id}", status_code=204)
def delete_term(term_id: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id).delete()
    db.commit()
    return None
