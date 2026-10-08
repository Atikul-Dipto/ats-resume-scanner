# Prottoy — the career center for job seekers

**Live**: https://atikul-dipto.github.io/ats-resume-scanner/

*Prottoy (প্রত্যয়) means "confidence".* ATS resume scanner, live resume builder and an
engineering & data job board for job seekers in Bangladesh, in one place.
(the API runs on Render's free tier — the first request after idle can take ~30–50s to wake up)

Scan an existing resume for ATS (Applicant Tracking System) problems, open it in a structured
builder pre-filled from your file, fix it against a **live** ATS score, tailor it to a job
posting, and export an ATS-safe PDF or DOCX. Then browse engineering and data jobs ranked by how
well your resume fits each one. Accounts are optional — they add saved resumes, versions, and
score history.

→ **[ARCHITECTURE.md](ARCHITECTURE.md)** for the system design, scaling model, data model,
security controls, and decision log.

## What it does

**Work Signal** (`/api/market`, `#/market`)
- Job-market signals computed only from Prottoy's real open listings, with no sample data:
  - most-demanded skills, with the last two weeks against the two before
  - companies hiring most, locations, and work-mode split
  - new jobs per week
  - median salary, counted only from postings that state one
- Every skill, company and number links to the postings behind it (`#/jobs?skill=…`).
- Shown alongside official Bangladesh labour statistics (unemployment, youth and graduate
  unemployment, participation, employment by sector) from the World Bank's public API (ILO modeled
  estimates, CC BY 4.0), fetched server-side and cached for a day.

**AI assistant** (`/api/assistant/*`, `backend/app/assistant`)
- A chat panel on every page, powered by Claude, that knows what you're looking at: your resume
  in the builder or scanner, a job posting, or the admin page.
- It works through tools over Prottoy's own data, so its facts match the UI:
  - It runs the real ATS scan.
  - It recommends jobs from the board, ranked by the same matcher.
  - It reads job postings.
  - It **suggests resume edits** (summary, headline, bullets, skills) that you apply or undo with
    one click.
- It writes summaries, cover letters and job descriptions. Admins can save a generated job
  description as a draft listing.
- It **learns**: goals and preferences you mention are remembered across chats. They're stored
  with your account, or in the browser when you're signed out, and you can view and delete them.
- It's off until `ANTHROPIC_API_KEY` is set; the UI hides it entirely until then. Usage is capped
  per person per day (`ASSISTANT_DAILY_LIMIT`) and per minute (`RATE_LIMIT_ASSISTANT`).

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
- Six templates, including four modelled on popular LaTeX resumes (Jake's Resume, moderncv,
  Awesome-CV, Harvard-style "Ivy"), all single-column and ATS-safe. Customize font, accent
  colour, sizes, margins, spacing, heading style, date placement, paper size and section order.
- A page-accurate preview: real A4/Letter pages in the same fonts as the PDF, with zoom,
  margin guides, full-screen mode and an "Exact PDF" view of the server-rendered file.
- Export to single-column, text-based PDF, DOCX or LaTeX source (or open it straight in
  Overleaf). The exported file scores the same as the editor showed — verified in tests for
  every template by exporting, re-parsing with the scanner, and comparing.
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

**Job ingestion** (`backend/app/ingest`, `python -m app.ingest.run`)
- Pulls jobs from many sources into the catalog every 6 hours (`.github/workflows/ingest.yml`):
  company career boards via the official Greenhouse, Lever, Ashby and SmartRecruiters APIs, the
  public job APIs, and — opt-in per site — schema.org `JobPosting` career pages and CSS-selector
  listing pages. Configure sources and keywords in [`sources.yaml`](backend/app/ingest/sources.yaml).
- Scraping honours robots.txt for every URL (failing closed) and only runs for sites whose terms
  you've confirmed allow it (`terms_ok: true`). Sites that forbid it (LinkedIn, Indeed, BDJobs…)
  aren't scraped — ask them for a feed instead.
- Only jobs reachable from Bangladesh are kept (on-site in Bangladesh, or remote and not limited to
  another country). Every job links to its original posting: **Apply** opens it in one click.
- To write to the live database, add the `DATABASE_URL` repository secret (Settings → Secrets and
  variables → Actions). Without it, scheduled runs are dry runs that only report what they'd import.

**Interface**
- Light/dark design with a three.js 3D hero (lazy-loaded, paused off-screen, reduced-motion aware),
  live stats and a live job feed on the landing page, scroll and hover motion throughout.

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

- **API** — Render (Docker, `render.yaml`) auto-deploys on every push to `main`; migrations run
  on container start (`backend/start.sh`). Two settings to add in the Render dashboard:
  `DATABASE_URL` — a free [Neon](https://neon.tech) or [Supabase](https://supabase.com) Postgres
  connection string, pasted as-is (without it, data resets on every restart and the UI says so);
  and `ADMIN_EMAILS` — your email, to unlock the job admin page. Everything else has safe defaults.
  To turn on the AI assistant, also add `ANTHROPIC_API_KEY`, a key from
  [console.anthropic.com](https://console.anthropic.com/). It's billed per use, with a daily cap
  per person. `ASSISTANT_MODEL` picks the model.
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
