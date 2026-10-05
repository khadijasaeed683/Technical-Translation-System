"""
Preprocessing Module (Table 5.1, row 3):
"Language/script detection (English vs. Urdu script vs. Roman Urdu), text
normalization, typo correction, short-form expansion."

This is intentionally rule/dictionary based rather than a trained model —
it is fast, fully explainable (every correction has a reason we can log to
the Diff/Audit Log, Section 10), and easy to extend by editing the two
dictionaries below. The base model + validation layer handle everything
this stage doesn't catch.
"""
import re
from dataclasses import dataclass, field
from typing import List, Tuple

URDU_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")

# Common Roman Urdu function words / spelling variants (Section 5.2 note on
# "hai/hy/h" style variants). Not exhaustive by design — meant to be grown
# over time the same way the glossary is (Section 10.2, "Dataset growth").
ROMAN_URDU_MARKERS = {
    "hai", "hy", "h", "kya", "kia", "nahi", "nahin", "nhi", "mujhe", "mjy", "mje",
    "apka", "apna", "yar", "yaar", "theek", "thik", "acha", "achha", "kal", "aj",
    "ab", "kyun", "kion", "hain", "raha", "rahi", "rahe", "chahiye", "samajh",
    "samjh", "milty", "milte", "system", "down",
}

# Short-form / abbreviation expansions (FR-05, TC-03, TC-04).
SHORT_FORM_EXPANSIONS = {
    "asap": "as soon as possible",
    "pls": "please",
    "plz": "please",
    "btw": "by the way",
    "u": "you",
    "r": "are",
    "ur": "your",
    "thx": "thanks",
    "tmrw": "tomorrow",
    "2mrw": "tomorrow",
    "2day": "today",
    "msg": "message",
    "info": "information",
}

# Common chat-typo -> correction map (TC-04: "sen"->send, "fyl"->file).
TYPO_CORRECTIONS = {
    "sen": "send",
    "fyl": "file",
    "recieve": "receive",
    "teh": "the",
    "definately": "definitely",
    "seperate": "separate",
}

# Roman Urdu short-form -> canonical Roman Urdu / meaning (TC-03: "mjy" -> "mujhe").
ROMAN_URDU_SHORTFORMS = {
    "mjy": "mujhe",
    "mje": "mujhe",
    "hy": "hai",
    "h": "hai",
    "kia": "kya",
    "nhi": "nahi",
    "nhin": "nahi",
}


@dataclass
class PreprocessResult:
    original_text: str
    normalized_text: str
    detected_lang: str  # "en" | "ur" | "ur-roman"
    corrections: List[str] = field(default_factory=list)  # human-readable reasons, feeds correction_reason


def detect_language(text: str) -> str:
    """FR-08: auto-detect English / Urdu script / Roman Urdu."""
    if URDU_SCRIPT_RE.search(text):
        return "ur"

    tokens = _tokenize(text)
    roman_hits = sum(1 for t in tokens if t in ROMAN_URDU_MARKERS)
    if tokens and roman_hits / len(tokens) >= 0.15:
        return "ur-roman"

    return "en"


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def normalize_and_correct(text: str, detected_lang: str) -> Tuple[str, List[str]]:
    """FR-06 (typo correction) + FR-05 (short-form expansion), applied before translation."""
    corrections: List[str] = []

    if detected_lang == "ur":
        # Urdu script text: light whitespace normalization only; jargon-level
        # correction happens in the validation layer via the glossary.
        return re.sub(r"\s+", " ", text).strip(), corrections

    words = text.split()
    out_words = []
    for w in words:
        stripped = re.sub(r"[^\w']", "", w).lower()
        suffix = w[len(stripped):] if stripped and w.lower().endswith(stripped) is False else ""
        replacement = None

        if detected_lang == "ur-roman" and stripped in ROMAN_URDU_SHORTFORMS:
            replacement = ROMAN_URDU_SHORTFORMS[stripped]
            corrections.append(f"roman_urdu_shortform: '{stripped}' -> '{replacement}'")
        elif stripped in SHORT_FORM_EXPANSIONS:
            replacement = SHORT_FORM_EXPANSIONS[stripped]
            corrections.append(f"shortform_expansion: '{stripped}' -> '{replacement}'")
        elif stripped in TYPO_CORRECTIONS:
            replacement = TYPO_CORRECTIONS[stripped]
            corrections.append(f"typo_fix: '{stripped}' -> '{replacement}'")

        if replacement:
            out_words.append(replacement)
        else:
            out_words.append(w)

    normalized = " ".join(out_words)
    return normalized, corrections


def preprocess(text: str, source_lang_hint: str = "auto") -> PreprocessResult:
    text = text.strip()
    detected = detect_language(text) if source_lang_hint == "auto" else source_lang_hint
    normalized, corrections = normalize_and_correct(text, detected)
    return PreprocessResult(
        original_text=text,
        normalized_text=normalized,
        detected_lang=detected,
        corrections=corrections,
    )


def default_target_for(source_lang: str) -> str:
    """EN<->UR, Roman Urdu -> EN (per Section 1.1 scope: three directions)."""
    if source_lang == "en":
        return "ur"
    return "en"  # both "ur" and "ur-roman" translate to English by default
