# ATS Resume Scanner + Builder + Job Board

**Live demo**: https://atikul-dipto.github.io/ats-resume-scanner/
(the API runs on Render's free tier — the first request after idle can take ~30–50s to wake up)

Scan an existing resume for ATS (Applicant Tracking System) problems, open it in a structured
builder pre-filled from your file, fix it against a **live** ATS score, tailor it to a job
posting, and export an ATS-safe PDF or DOCX. Then browse engineering and data jobs ranked by how
well your resume fits each one. Accounts are optional — they add saved resumes, versions, and
score history.

→ **[ARCHITECTURE.md](ARCHITECTURE.md)** for the system design, scaling model, data model,
security controls, and decision log.

## What it does

**Scan** (`/api/analyze`)
- Parses `.pdf` (pdfplumber) and `.docx` (python-docx) in memory — uploads are never stored.
- Flags structural risks ATS parsers choke on: images, tables, real multi-column layouts
  (gutter detection — dense single-column pages aren't false-flagged), contact info in a
  header/footer, length.
- Detects standard sections, scores content (action verbs, quantified bullets) and keyword
  match against a target job description (TF-IDF + skills vocabulary), with actionable fixes.
- Returns a best-effort structured draft of the file so it can be opened in the builder.

**Build** (`/api/builder/*`, `/api/resumes/*`)
- Structured editor for contact info, experience, education, skills, projects, certifications.
- Live score while typing (debounced, ~6 ms server-side), with coaching shown under the exact
  bullet that's weak and one-click adds for keywords missing from the target job.
- Export to single-column, text-based PDF or DOCX. The exported file scores the same as the
  editor showed — verified in tests by exporting, re-parsing with the scanner, and comparing.
- Anonymous drafts autosave in the browser; signed-in users get saved resumes with optimistic
  locking (two tabs can't silently overwrite each other) and per-resume score history.

**Job board** (`/api/jobs`, `/api/jobs/match`, `/api/admin/jobs`)
- Engineering & data catalog in five disciplines: Data & Analytics (data/business analyst, BI,
  data engineering), Software & IT, Civil & Construction, Electrical & Electronics, and
  Mechanical, Industrial & Textile.
- Local (Bangladesh) listings are posted by admins (`ADMIN_EMAILS`); remote roles are imported
  from the public job APIs below, classified by discipline, and refreshed in the background.
- **Match me**: upload a resume, or use the builder draft / a saved resume, and every listing gets
  a match score with the skills you have, the skills you're missing, and an experience-fit note.
  The detected discipline is pre-selected. "Tailor my resume for this job" opens the builder with
  that posting as the target job.

**Live job search** (`/api/jobs/search`)
- Queries documented public APIs concurrently — [Remotive](https://remotive.com/api-documentation),
  [Arbeitnow](https://www.arbeitnow.com/api/job-board-api), [The Muse](https://www.themuse.com/developers/api/v2),
  and optionally [Adzuna](https://developer.adzuna.com/) — with caching, a per-request deadline,
  and per-provider failure isolation. No scraping.
- Ranks by keyword/title overlap re-ranked by a from-scratch two-tower encoder (trained with
  TensorFlow, served as plain NumPy) — see the [model card](backend/app/matching/MODEL_CARD.md).

## Stack

| | |
|---|---|
| Frontend | React 18, Vite, React Router — static on GitHub Pages |
| API | FastAPI, SQLAlchemy 2, Alembic, PyJWT, pdfplumber, python-docx, fpdf2, scikit-learn, NumPy |
| Data | Postgres (Neon/Supabase free tier) in production, SQLite locally; optional Redis |
| Training | TensorFlow/Keras (dev-only, `requirements-train.txt`) |

## Running locally

```bash
# Backend (Python 3.12)
cd backend
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
alembic upgrade head          # creates ./data/app.db (SQLite)
uvicorn app.main:app --reload # http://localhost:8000/docs

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173/ats-resume-scanner/
```

Production-shaped stack (Postgres + Redis + API) instead of SQLite:

```bash
docker compose up --build
```

All configuration is environment variables — see [`backend/.env.example`](backend/.env.example).

## Tests & checks

```bash
cd backend
ruff check .
pytest                                                   # SQLite
TEST_DATABASE_URL=postgresql://user:pass@localhost/db pytest   # same suite on Postgres

cd ../frontend
npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs all of the above on every PR, including the backend suite
against a real Postgres service and `alembic check` to catch models changed without a migration.

## Deployment

- **API** — `render.yaml` is a Render Blueprint (Docker). It generates `JWT_SECRET` and prompts
  for `DATABASE_URL`; paste a [Neon](https://neon.tech) or [Supabase](https://supabase.com)
  Postgres connection string as-is. Migrations run on container start (`backend/start.sh`).
- **Frontend** — `.github/workflows/deploy.yml` builds to GitHub Pages on push to `main`. Set
  the repository variable `VITE_API_BASE_URL` to the API's URL.
- **Scaling past one instance** — set `REDIS_URL` and move migrations to a release step
  (`RUN_MIGRATIONS=0`). The full staged plan is in [ARCHITECTURE.md §6](ARCHITECTURE.md#6-scaling-model).

## Retraining the matching encoder

```bash
cd backend
pip install -r requirements-train.txt
python -m app.matching.train   # reads anonymized events from DATABASE_URL
```
