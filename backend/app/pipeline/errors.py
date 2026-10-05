"""
Shared error types for the Gemini-backed pipeline stages.

A 429 from Gemini used to be indistinguishable from any other failure: the base
model surfaced it as a generic 502, and the validation layer silently fell back
to the raw output (which is why "validated" looked identical to "raw").
QuotaExceededError lets callers tell "out of quota" apart from other errors.
"""
import re
from typing import Optional

from google.api_core.exceptions import ResourceExhausted


class QuotaExceededError(Exception):
    def __init__(self, message: str, retry_after: Optional[float] = None, daily: bool = False):
        super().__init__(message)
        self.retry_after = retry_after  # seconds, if Google told us
        self.daily = daily              # True when it's the per-day (RPD) limit


def as_quota_error(exc: Exception) -> Optional[QuotaExceededError]:
    """Return a QuotaExceededError if `exc` is a Gemini 429/quota error, else None."""
    text = str(exc)
    if not (isinstance(exc, ResourceExhausted) or "quota" in text.lower() or "429" in text):
        return None

    match = re.search(r"retry in ([\d.]+)s", text)
    retry_after = float(match.group(1)) if match else None
    daily = "PerDay" in text  # e.g. GenerateRequestsPerDayPerProjectPerModel-FreeTier
    return QuotaExceededError(text, retry_after=retry_after, daily=daily)