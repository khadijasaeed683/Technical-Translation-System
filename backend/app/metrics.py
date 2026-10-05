"""
Prometheus metrics for the translation pipeline.

These are plain prometheus_client objects (Counter/Histogram/Gauge) kept in
one place so every module that needs to record something imports from here
instead of defining its own. prometheus-fastapi-instrumentator (wired up in
main.py) exposes these - plus its own built-in HTTP metrics - on GET /metrics,
which Prometheus scrapes on a timer and Grafana reads from Prometheus.

Label cardinality note: GEMINI_TOKENS and TRANSLATION_REQUESTS are labeled by
user_email. That's fine for a handful of users (a class project, an internal
tool) but would be a bad idea with thousands of distinct users, since
Prometheus keeps a separate time series PER label combination forever (until
it ages out). If this ever grows past a few dozen users, switch the label to
a user_id bucket or drop it and keep per-user totals in Postgres instead.
"""
from prometheus_client import Counter, Gauge, Histogram

# --- Request-level outcomes ---
TRANSLATION_REQUESTS = Counter(
    "translation_requests_total",
    "Total /translate requests, by language pair and outcome",
    ["source_lang", "target_lang", "status"],  # status: ok | fallback | error
)

TRANSLATIONS_IN_PROGRESS = Gauge(
    "translation_requests_in_progress",
    "Translation requests currently being processed",
)

# --- Pipeline step timing (reuses the same steps shown in the UI trace) ---
PIPELINE_STEP_DURATION = Histogram(
    "pipeline_step_duration_seconds",
    "Duration of each pipeline step",
    ["step_name"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 16),
)

# --- Gemini usage ---
GEMINI_CALLS = Counter(
    "gemini_calls_total",
    "Gemini API calls, by pipeline role and outcome",
    ["role", "status"],  # role: base_translation | validation | evaluation_*; status: ok | error
)

GEMINI_TOKENS = Counter(
    "gemini_tokens_total",
    "Gemini tokens consumed, by user, pipeline role, and token type",
    ["user_email", "role", "token_type"],  # token_type: prompt | completion
)

VALIDATION_FALLBACKS = Counter(
    "validation_fallbacks_total",
    "Times the validation layer failed and the raw base-model output was served instead",
)

TRANSLATION_CONFIDENCE = Histogram(
    "translation_confidence_score",
    "Validator-reported confidence scores (0-1) for successfully validated translations",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)