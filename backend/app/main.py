import json
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import GlossaryTerm
from app.routers import admin, auth, evaluation, feedback, glossary, history, translate

# Print the per-step pipeline log in `docker compose logs backend`.
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logging.getLogger("translation").setLevel(logging.INFO)

app = FastAPI(
    title="Bilingual Translation System (EN <-> UR <-> Roman Urdu)",
    description="Validating-wrapper translation system: base model + validation/correction layer + glossary + feedback + evaluation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(translate.router)
app.include_router(history.router)
app.include_router(feedback.router)
app.include_router(glossary.router)
app.include_router(admin.router)
app.include_router(evaluation.router)

# Prometheus: adds built-in HTTP metrics (request count, latency, in-progress,
# by method/path/status) AND exposes everything defined in app/metrics.py
# (both use the same prometheus_client default registry), all on GET /metrics.
# Prometheus (the separate container in docker-compose.yml) scrapes that
# endpoint every 10s; Grafana reads from Prometheus. See the README section
# on observability for the full explanation.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/health")
def health():
    return {"status": "ok"}


def _seed_glossary():
    seed_path = os.path.join(os.path.dirname(__file__), "seed_data", "glossary_seed.json")
    with open(seed_path, encoding="utf-8") as f:
        terms = json.load(f)

    db = SessionLocal()
    try:
        if db.query(GlossaryTerm).count() > 0:
            return
        for t in terms:
            db.add(GlossaryTerm(**t))
        db.commit()
    finally:
        db.close()


def _add_missing_columns():
    """
    create_all() only creates missing TABLES, it never alters existing ones.
    This adds the diff_logs.trace column to databases created before step
    tracing existed, so nobody has to wipe their Postgres volume.
    """
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE diff_logs ADD COLUMN IF NOT EXISTS trace JSONB"))


@app.on_event("startup")
def on_startup():
    # For an MVP/FYP-scale deployment, create-all is simpler than managing
    # Alembic migrations. Swap for Alembic if this needs to survive schema
    # changes across environments.
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    _seed_glossary()
