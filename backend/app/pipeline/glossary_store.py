"""
Glossary / Terminology Store lookup.

Simple substring/alias matching against the input text — deliberately
simple and fast rather than a semantic
search. Good enough for a curated, growing glossary; can be swapped for an
embedding-based lookup later without touching the validation layer's
interface (it just calls find_relevant_terms()).
"""
import re
from typing import List

from sqlalchemy.orm import Session

from app.models import GlossaryTerm


def find_relevant_terms(db: Session, text: str, limit: int = 20) -> List[GlossaryTerm]:
    tokens = set(re.findall(r"[\w']+", text.lower()))
    if not tokens:
        return []

    all_terms = db.query(GlossaryTerm).all()
    matches = []
    for gt in all_terms:
        candidates = {gt.term.lower()}
        candidates.update((a.lower() for a in (gt.aliases or [])))
        candidates.update((v.lower() for v in (gt.roman_urdu_variants or [])))
        if tokens & candidates or any(c in text.lower() for c in candidates if " " in c):
            matches.append(gt)
        if len(matches) >= limit:
            break
    return matches


def format_glossary_for_prompt(terms: List[GlossaryTerm]) -> str:
    if not terms:
        return "(no glossary terms matched this input)"
    lines = []
    for t in terms:
        aliases = ", ".join(t.aliases or [])
        lines.append(
            f"- '{t.term}' ({t.domain}) -> canonical translation/handling: "
            f"'{t.canonical_translation}'"
            + (f"; aliases/short-forms: {aliases}" if aliases else "")
        )
    return "\n".join(lines)
