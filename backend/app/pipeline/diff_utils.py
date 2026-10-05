"""
Change-Detection / Diff Module (Table 5.1, row 7; Section 10).

Computes a structured, word-level diff between the base model's raw output
and the validation layer's corrected output. This is what gets stored in
the Diff/Audit Log and is the basis for:
  - correction-rate metrics (Section 10.2 "Evaluation")
  - debugging which layer introduced/missed an error (Section 10.2 "Debugging & trust")
"""
import difflib
from typing import List, TypedDict


class DiffOp(TypedDict):
    op: str  # "equal" | "insert" | "delete" | "replace"
    raw: str
    validated: str


def compute_word_diff(raw_output: str, validated_output: str) -> List[DiffOp]:
    raw_words = raw_output.split()
    val_words = validated_output.split()

    sm = difflib.SequenceMatcher(a=raw_words, b=val_words, autojunk=False)
    ops: List[DiffOp] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue  # only store the deltas — unchanged text isn't useful audit signal
        op_name = {"replace": "replace", "delete": "delete", "insert": "insert"}[tag]
        ops.append(
            DiffOp(
                op=op_name,
                raw=" ".join(raw_words[i1:i2]),
                validated=" ".join(val_words[j1:j2]),
            )
        )
    return ops


def has_meaningful_diff(diff_ops: List[DiffOp]) -> bool:
    return len(diff_ops) > 0
