"""
Automatic metrics (Section 7.1): "Automatic metrics (BLEU, chrF++) give a
coarse quality signal ... paired with human fluency scoring ... plus a
dedicated 'terminology accuracy' rate measured only on the jargon subset."

BLEU/chrF++ are computed with sacrebleu (the standard, citable implementation
used in MT research) so the numbers are directly comparable to literature
baselines. Terminology accuracy is a simple custom check: for jargon-tagged
sentences, does the system's/baseline's output contain the expected term
verbatim (rather than a paraphrase/mistranslation of it)?
"""
from typing import Dict, List

import sacrebleu


def corpus_bleu(hypotheses: List[str], references: List[str]) -> float:
    if not hypotheses:
        return 0.0
    bleu = sacrebleu.corpus_bleu(hypotheses, [references])
    return round(bleu.score, 2)


def corpus_chrf(hypotheses: List[str], references: List[str]) -> float:
    if not hypotheses:
        return 0.0
    chrf = sacrebleu.corpus_chrf(hypotheses, [references], word_order=2)  # word_order=2 -> chrF++
    return round(chrf.score, 2)


# A handful of "must survive translation verbatim" terms used to approximate
# the "terminology accuracy" metric from Section 7.1 on the jargon subset.
_EXPECTED_JARGON_SURVIVORS = [
    "api", "bug", "push", "prod", "pr", "ci", "docker", "git", "rebase",
    "server", "429", "compile", "branch", "pipeline", "container",
]


def terminology_accuracy(hypotheses: List[str], sources: List[str]) -> float:
    """
    Rough proxy for Table 7.1's "terminology accuracy" row: of the jargon
    tokens present in the source sentence, what fraction survive (case-
    insensitively) into the hypothesis? This rewards keeping/transliterating
    technical terms correctly and penalizes translating them away.
    """
    total_terms = 0
    survived = 0
    for src, hyp in zip(sources, hypotheses):
        src_lower = src.lower()
        hyp_lower = hyp.lower()
        for term in _EXPECTED_JARGON_SURVIVORS:
            if term in src_lower:
                total_terms += 1
                if term in hyp_lower:
                    survived += 1
    if total_terms == 0:
        return 0.0
    return round(survived / total_terms * 100, 2)


def build_metrics_table(
    references: List[str],
    sources: List[str],
    google_hyp: List[str],
    raw_base_hyp: List[str],
    our_system_hyp: List[str],
) -> Dict[str, Dict[str, float]]:
    """Matches the Table 7.1 structure: rows = metrics, columns = the three systems."""
    return {
        "bleu_overall": {
            "google_translate": corpus_bleu(google_hyp, references),
            "raw_base_model": corpus_bleu(raw_base_hyp, references),
            "our_system": corpus_bleu(our_system_hyp, references),
        },
        "chrf_overall": {
            "google_translate": corpus_chrf(google_hyp, references),
            "raw_base_model": corpus_chrf(raw_base_hyp, references),
            "our_system": corpus_chrf(our_system_hyp, references),
        },
        "terminology_accuracy_jargon_subset": {
            "google_translate": terminology_accuracy(google_hyp, sources),
            "raw_base_model": terminology_accuracy(raw_base_hyp, sources),
            "our_system": terminology_accuracy(our_system_hyp, sources),
        },
    }
