# Bilingual Translation System (English ↔ Urdu ↔ Roman Urdu)

Implementation of the system described in `Translation_System_Design_Document.docx`:
a validating-wrapper translator — a base LLM (Gemini) produces a raw translation,
then a dedicated **validation & correction layer** (also Gemini, given glossary
context) checks and fixes it, specifically targeting technical jargon and
Roman Urdu / short-form / typo handling that general translators get wrong.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Base model + validation layer | **Gemini API** | One provider, two roles (raw translate + a second "critic/corrector" call). Swappable — see `app/pipeline/base_model.py`. |
| Backend | **FastAPI** | Async, typed, good fit for the pipeline architecture in Section 5. |
| Database | **PostgreSQL** | Matches Section 5.4's five data stores (users, history, glossary, feedback, diff/audit log). |
| Frontend | **React + Vite** | RTL/LTR mixed rendering, SPA. |
| Evaluation | `sacrebleu` (BLEU/chrF++) + `deep-translator` (free Google Translate baseline) | Implements Section 6–7's 3-way comparison. |

## What's implemented, mapped to the design doc

- **FR-01–FR-14, NFR-01–NFR-08**: see inline comments in `backend/app/` — every
  router/module references the requirement IDs it implements.
- **Pipeline (Section 5.3)**: `routers/translate.py` runs preprocessing →
  base model → validation layer (+glossary) → diff computation → history/audit
  storage, in that order.
- **Fallback (UC-09, NFR-04)**: if the validation layer times out or errors,
  `translate.py` catches it and serves the raw base-model output, flagged
  `is_validated: false`.
- **Diff/Audit Log (Section 10)**: every request stores a `DiffLog` row with a
  word-level diff (`pipeline/diff_utils.py`) and the correction reasons.
- **Evaluation (Section 6–7)**: `backend/app/seed_data/eval_dataset.csv` ships
  ~30 sentence pairs across the five domains in Table 6.1 (general, CS jargon,
  Roman Urdu, formal, idiomatic) with human references — same schema as
  Section 6.3, so you can grow it toward the 1,000–1,500 target by appending
  rows, no code changes needed. `POST /evaluation/run` (admin-only) runs
  Google Translate vs raw Gemini vs your validated system against it and
  reports BLEU / chrF++ / a jargon "terminology accuracy" proxy, matching the
  Table 7.1 layout.
- **Admin dashboard (FR-14)**: `GET /admin/analytics` — feedback trends,
  correction rate, fallback rate, top correction reasons.

## Prerequisites

- Docker + Docker Compose (recommended — this is the easiest way to run everything)
- A **Gemini API key**: https://aistudio.google.com/app/apikey (free tier works)

## Running it (Docker — recommended)

```bash
# 1. From the project root, copy the env template and fill in your key
cp .env.example .env
# edit .env: set GEMINI_API_KEY, and optionally JWT_SECRET_KEY / ADMIN_EMAIL

# 2. Start everything (Postgres + backend + frontend)
docker compose up --build

# 3. Open the app
# Frontend:      http://localhost:5173
# Backend docs:  http://localhost:8000/docs   (interactive Swagger UI)
```

First run takes a minute (npm install + pip install happen inside the build).
Postgres data persists in a Docker volume (`db_data`) across restarts.

**First account = admin:** whichever email matches `ADMIN_EMAIL` in `.env`
(default `admin@example.com`) is automatically granted admin rights (glossary
editing, `/admin` dashboard, running evaluations) the moment they sign up.
Sign up with that email first if you want admin access.

To stop: `Ctrl+C`, then `docker compose down` (add `-v` to also wipe the DB volume).

## Running it without Docker (manual)

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Point at a Postgres instance you already have running, e.g.:
export DATABASE_URL="postgresql+psycopg2://translator:translator@localhost:5432/translation_system"
export GEMINI_API_KEY="your-key-here"
export JWT_SECRET_KEY="some-long-random-string"

uvicorn app.main:app --reload --port 8000
```
You'll need a Postgres server running locally with a `translation_system` database
and a `translator` user (or edit `DATABASE_URL` to match whatever you have).

### Frontend
```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```
Open http://localhost:5173

## Using the evaluation module

Log in as the admin account, go to **Admin** in the nav bar, click
**"Run new evaluation"**. This calls the Gemini API once per sentence for the
raw baseline, once more for the validated system, plus the free Google
Translate wrapper for Baseline A — so ~90 external calls for the 30-sentence
seed set. Results (BLEU, chrF++, jargon terminology accuracy) are stored and
shown in a table matching the doc's Table 7.1 layout; `GET /evaluation/results`
returns past runs too.

To grow the dataset toward the 1,000–1,500 sentence target in Section 6.4,
append rows to `backend/app/seed_data/eval_dataset.csv` following the same
columns — no code changes required.

## Extending the glossary

The seed glossary (`backend/app/seed_data/glossary_seed.json`) only loads once
(on first startup, if the table is empty). After that, manage terms from the
**Glossary** page in the UI (admin-only add/delete) or via the API
(`POST/PUT/DELETE /glossary`).

## Swapping the base model (NFR-07)

`backend/app/pipeline/base_model.py` defines a `BaseTranslationModel`
interface with one method, `translate()`. `GeminiBaseModel` is the only
implementation wired up; to swap in GPT, NLLB, or a commercial MT API, add a
new subclass and change what `get_base_model()` returns. The validation layer
(`pipeline/validation.py`) is untouched by this — it only depends on getting
a raw translation string, per the doc's separation-of-concerns design
(Section 5.1).

## Project structure

```
translation_system/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # FastAPI app, CORS, startup (table creation + glossary seed)
│       ├── config.py            # env-driven settings
│       ├── database.py          # SQLAlchemy engine/session
│       ├── models.py            # User, Translation, GlossaryTerm, Feedback, DiffLog, EvaluationRun
│       ├── schemas.py           # Pydantic request/response models
│       ├── auth.py / deps.py    # JWT + password hashing, auth dependencies
│       ├── routers/             # auth, translate, history, feedback, glossary, admin, evaluation
│       ├── pipeline/            # preprocessing, base_model, validation, glossary_store, diff_utils
│       ├── evaluation/          # dataset loader, BLEU/chrF++ metrics, 3-way runner
│       └── seed_data/           # glossary_seed.json, eval_dataset.csv
└── frontend/
    ├── Dockerfile / nginx.conf
    └── src/
        ├── api.js               # fetch wrapper for the backend
        ├── context/AuthContext.jsx
        ├── components/          # NavBar, ConfidenceBadge, FeedbackButtons
        └── pages/                # Login, Signup, Translate, History, Glossary, Admin
```

## Known scope notes

- The evaluation dataset ships with ~30 curated sentence pairs, not the full
  1,000–1,500 target — that requires bilingual human annotators per Section
  6.2, which is outside what a code deliverable can produce. The schema and
  pipeline are built to scale to that size directly.
- Preprocessing (typo/short-form correction, Roman Urdu detection) is
  dictionary/rule-based rather than a trained model — fast, explainable, and
  easy to extend (see `pipeline/preprocessing.py`), matching what the
  validation layer needs to log as `correction_reason`.
- Table 5.1's "API Gateway" (rate limiting, routing) is handled minimally —
  FastAPI + CORS — since a full gateway (e.g. Kong/nginx rate limiting) is
  infrastructure, not application logic; add it at deploy time if needed.
