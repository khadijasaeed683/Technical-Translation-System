"""
Data stores, as specified in Section 5.4 of the design document:
  - User & Auth DB
  - History DB              (source_text, source_lang, raw_output, validated_output, timestamp)
  - Glossary DB              (term, domain, canonical_translation, aliases, roman_urdu_variants)
  - Feedback DB              (translation_id, rating, comment, timestamp)
  - Diff / Audit Log         (translation_id, raw_output, validated_output, diff, correction_reason, trace)
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class LanguageCode(str, enum.Enum):
    en = "en"
    ur = "ur"
    ur_roman = "ur-roman"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    translations = relationship("Translation", back_populates="user", cascade="all, delete-orphan")


class Translation(Base):
    """History DB — one row per translation request (FR-03, FR-11)."""

    __tablename__ = "translations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)

    source_text = Column(Text, nullable=False)
    source_lang = Column(String, nullable=False)   # en / ur / ur-roman
    target_lang = Column(String, nullable=False)

    raw_output = Column(Text, nullable=False)        # base model's untouched output
    validated_output = Column(Text, nullable=False)  # after validation layer
    final_output = Column(Text, nullable=False)      # user-facing output, editable after translation
    confidence = Column(Float, nullable=True)
    alternates = Column(JSONB, nullable=True)        # list[str] of alternate renderings (FR-10)
    is_validated = Column(Boolean, default=True)     # False if fell back to raw (UC-09 / NFR-04)

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="translations")
    feedback = relationship("Feedback", back_populates="translation", uselist=False, cascade="all, delete-orphan")
    diff_log = relationship("DiffLog", back_populates="translation", uselist=False, cascade="all, delete-orphan")


class GlossaryTerm(Base):
    """Glossary / Terminology Store (FR-09, Table 5.1 #6)."""

    __tablename__ = "glossary_terms"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    term = Column(String, nullable=False, index=True)
    domain = Column(String, nullable=False, default="general")
    canonical_translation = Column(String, nullable=False)
    aliases = Column(JSONB, nullable=True)              # list[str] short forms / abbreviations
    roman_urdu_variants = Column(JSONB, nullable=True)  # list[str] e.g. ["hai", "hy", "h"]
    created_at = Column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    """Feedback DB (FR-07, UC-05)."""

    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    translation_id = Column(UUID(as_uuid=False), ForeignKey("translations.id"), nullable=False, unique=True)
    rating = Column(String, nullable=False)  # "up" | "down"
    comment = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    translation = relationship("Translation", back_populates="feedback")


class DiffLog(Base):
    """Diff / Audit Log (Section 10)."""

    __tablename__ = "diff_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    translation_id = Column(UUID(as_uuid=False), ForeignKey("translations.id"), nullable=False, unique=True)

    raw_output = Column(Text, nullable=False)
    validated_output = Column(Text, nullable=False)
    diff = Column(JSONB, nullable=False)                # structured token-level diff ops
    correction_reason = Column(JSONB, nullable=True)    # list[str]: glossary_substitution, typo_fix, ...
    confidence_before = Column(Float, nullable=True)
    confidence_after = Column(Float, nullable=True)
    trace = Column(JSONB, nullable=True)                # step-by-step pipeline log (preprocessing -> validation)
    timestamp = Column(DateTime, default=datetime.utcnow)

    translation = relationship("Translation", back_populates="diff_log")


class EvaluationRun(Base):
    """Stores results of an evaluation pass (Section 6 & 7)."""

    __tablename__ = "evaluation_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    triggered_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    dataset_size = Column(Integer, nullable=False)
    metrics = Column(JSONB, nullable=False)  # Table 7.1 structure, see evaluation/metrics.py
    per_sentence_results = Column(JSONB, nullable=True)  # Section 7.3 examples
    timestamp = Column(DateTime, default=datetime.utcnow)