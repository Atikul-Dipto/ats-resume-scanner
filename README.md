# ATS Resume Scanner

Scans a resume for ATS (Applicant Tracking System) compatibility — formatting risks, missing
sections, weak content, keyword gaps against a target job description — then searches live job
boards for roles that match the candidate's extracted title, skills, and experience.

## How it works

**Resume analysis** (`backend/app/analysis`)
- Parses `.pdf` (pdfplumber) and `.docx` (python-docx), flagging structural risks ATS parsers
  choke on: embedded images, tables, multi-column layouts, contact info stuck in a header/footer.
- Detects standard resume sections (Contact, Summary, Experience, Education, Skills).
- Extracts a candidate profile: emails, phone, links, skills (matched against a curated skills
  list), years of experience, and current title — all scoped to the Experience section so it
  doesn't confuse education dates with work history.
- If a job description is supplied, scores keyword overlap via TF-IDF cosine similarity plus
  direct skill-list matching, and reports matched vs. missing keywords.
- Combines formatting, content quality (bullet points, action verbs, quantified achievements),
  and keyword scores into a single 0–100 ATS score with actionable suggestions.

**Job search** (`backend/app/jobs`)
- Queries free, key-less public job APIs concurrently: [Remotive](https://remotive.com/api-documentation),
  [Arbeitnow](https://www.arbeitnow.com/api/job-board-api), [The Muse](https://www.themuse.com/developers/api/v2).
- Optionally queries [Adzuna](https://developer.adzuna.com/) if `ADZUNA_APP_ID`/`ADZUNA_APP_KEY`
  are set (free registration, location-based search).
- Deduplicates results, ranks by keyword/title overlap with the resume's extracted title and
  skills, and drops zero-relevance noise.

No scraping — job-board Terms of Service generally prohibit it, and it's fragile. Everything here
goes through documented, public APIs.

## Stack

- **Backend**: FastAPI, pdfplumber, python-docx, scikit-learn, httpx
- **Frontend**: React + Vite

## Running locally

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate   # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env` in each folder if you need to override defaults (API base URL,
allowed CORS origins, Adzuna keys).

## Tests

```bash
cd backend
pytest
```

## Deployment

- **Backend**: containerized via the included `Dockerfile` — deploy to Render, Railway, or Fly.io.
  Set `ALLOWED_ORIGINS` to your deployed frontend URL.
- **Frontend**: static build (`npm run build`) — deploy to Vercel, Netlify, or GitHub Pages. Set
  `VITE_API_BASE_URL` to your deployed backend URL.
