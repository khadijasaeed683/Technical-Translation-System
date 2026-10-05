"""
Loads the evaluation dataset (Section 6: "manually curated sentence pairs...
targeting technical/Roman-Urdu/idiomatic domains", schema in Section 6.3).

The seed CSV ships with ~30 sentence pairs across the five domains from
Table 6.1 (general, technical/CS jargon, Roman Urdu, formal, idiomatic).
Section 6.4 targets 1,000-1,500 pairs for stable BLEU/chrF++ estimates —
this seed set is structured with the exact same schema so it can be grown
to that size by appending rows to eval_dataset.csv (or loading from a
versioned source) without any code changes.
"""
import csv
import os
from dataclasses import dataclass
from typing import List, Optional

_SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "seed_data", "eval_dataset.csv")


@dataclass
class EvalSentencePair:
    id: str
    source_text: str
    source_lang: str
    target_lang: str
    domain: str
    human_reference: str
    contains_jargon: bool
    contains_typo_or_shortform: bool
    annotator_notes: str


def load_eval_dataset(sample_size: Optional[int] = None) -> List[EvalSentencePair]:
    pairs: List[EvalSentencePair] = []
    with open(_SEED_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pairs.append(
                EvalSentencePair(
                    id=row["id"],
                    source_text=row["source_text"],
                    source_lang=row["source_lang"],
                    target_lang=row["target_lang"],
                    domain=row["domain"],
                    human_reference=row["human_reference"],
                    contains_jargon=row["contains_jargon"].lower() == "true",
                    contains_typo_or_shortform=row["contains_typo_or_shortform"].lower() == "true",
                    annotator_notes=row.get("annotator_notes", ""),
                )
            )
    if sample_size:
        pairs = pairs[:sample_size]
    return pairs
