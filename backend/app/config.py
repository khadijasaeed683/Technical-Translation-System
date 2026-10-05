"""
Central app configuration, loaded from environment variables (.env).
Nothing here is hard-coded so the system can be deployed/run anywhere.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

# Single-model default. Quotas are counted PER MODEL, so the base translator and
# the validator can point at two different models (see GEMINI_BASE_MODEL /
# GEMINI_VALIDATION_MODEL below) to double your free-tier daily allowance.
_DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class Settings:
    # --- Database ---
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://translator:translator@localhost:5432/translation_system",
    )

    # --- Auth / JWT ---
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-this-secret-in-prod")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24h

    # --- Gemini ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = _DEFAULT_MODEL
    # Role-specific models. Leave unset to use GEMINI_MODEL for both roles.
    GEMINI_BASE_MODEL: str = os.getenv("GEMINI_BASE_MODEL", _DEFAULT_MODEL)
    GEMINI_VALIDATION_MODEL: str = os.getenv("GEMINI_VALIDATION_MODEL", _DEFAULT_MODEL)

    # --- Pipeline behavior (NFR-01, NFR-04) ---
    VALIDATION_TIMEOUT_SECONDS: float = float(os.getenv("VALIDATION_TIMEOUT_SECONDS", "8"))
    BASE_MODEL_TIMEOUT_SECONDS: float = float(os.getenv("BASE_MODEL_TIMEOUT_SECONDS", "8"))

    # --- Evaluation (each sentence costs ~2 Gemini calls) ---
    # Pause between sentences so per-minute limits aren't tripped.
    EVAL_CALL_DELAY_SECONDS: float = float(os.getenv("EVAL_CALL_DELAY_SECONDS", "4"))
    # 0 = use the whole dataset. Set e.g. 5 on the free tier.
    EVAL_DEFAULT_SAMPLE_SIZE: int = int(os.getenv("EVAL_DEFAULT_SAMPLE_SIZE", "0"))

    # --- CORS ---
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    # --- Admin bootstrap (first admin account) ---
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
