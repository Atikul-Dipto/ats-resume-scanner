# Model Card: Resume↔Job Matching Encoder

## Purpose

A shared text encoder that embeds resumes and job postings into the same
vector space, so cosine similarity in either direction ("which jobs fit this
resume" / "which resumes fit this job") is a meaningful signal. It re-ranks
the existing keyword-overlap job search (`app/jobs/aggregator.py`) rather
than replacing it — it can surface semantically related roles the keyword
heuristic misses (e.g. "BI Analyst" for a "Data Analyst" resume with no
literal skill-string overlap).

## Architecture

Single shared (Siamese) tower: `TextVectorization → Embedding(64) →
GlobalAveragePooling1D → Dense(128, relu) → Dense(64) → L2-normalize`.
One encoder for both resumes and job postings — they're the same kind of
content (free text describing skills/titles/experience), so a genuinely
two-tower architecture with separately-learned weights isn't justified here.

Trained with in-batch-negative contrastive loss (`app/matching/model.py`):
for a batch of N (anchor, positive) pairs, the N×N similarity matrix has
true pairs on the diagonal and every other in-batch pairing as an implicit
negative.

## Training data — and its limits

**There is no historical hiring-outcome data and no resume corpus.** The app
never persists raw resumes, and no labeled "this candidate matched this job"
data exists anywhere. Training data is honestly limited to:

1. **Bootstrap (current)**: real job postings pulled live from Remotive,
   Arbeitnow, and The Muse across 16 diverse queries. For each posting,
   `(title + company)` is the anchor (short, profile-like text) and the full
   description is the positive (longer, job-like text) — two views of the
   *same* real posting. This teaches the encoder which titles/skills/
   descriptions cluster together, without fabricating any label.
2. **Usage flywheel (accumulates over time)**, two independent sources, both
   in `backend/data/events.db`, both anonymized — never raw resume text,
   name, email, or phone:
   - `match_events`, logged from `/api/jobs/search`: the query (title +
     skills) and its top matches.
   - `resume_scans`, logged from `/api/analyze`: title + skills + years of
     experience + the resulting ATS scores, one row per scan — captures
     every scan, not only the ones that go on to search jobs.

   `train.py` folds both in as additional pairs on the next retrain.

Last training run: **119 pairs** from ~120 unique postings, in-batch
retrieval accuracy 1.00 after 12 epochs. That accuracy number is optimistic
and should not be read as generalization performance — with a batch size of
32, it only means the encoder can tell each pair's positive apart from 31
random in-batch negatives, on a corpus small enough to plausibly
memorize. There is no held-out real-world test set because no
ground-truth-labeled matches exist yet.

## Known limitations

- **No real match-quality ground truth.** Everything above is a proxy signal
  (self-supervised structure + an existing keyword heuristic), not verified
  hiring outcomes.
- **Small, English-language, general-role corpus.** Remotive skews
  tech/remote; deep coverage of specialized or non-English-speaking labor
  markets is unlikely.
- **Ephemeral storage in production.** Render's free tier has no persistent
  disk — `backend/data/events.db` resets on every redeploy. The flywheel
  only accumulates data between deploys, not indefinitely. A real deployment
  would need a persistent volume or external database.
- **No fairness/bias audit.** The encoder has not been evaluated for
  systematic bias across demographic groups, industries, or role types.

## Appropriate use

Re-ranking signal inside this portfolio project's job search, and as a
demonstration of a from-scratch two-tower matching model with an honest,
real (not fabricated) training pipeline.

## Inappropriate use

Anything resembling real hiring or candidate-screening decisions. This has
not been validated against real outcomes and was never intended to make or
influence actual employment decisions about specific people.

## Retraining

```bash
cd backend
pip install -r requirements-train.txt   # TensorFlow, training-only
python -m app.matching.train
```

Re-run periodically as `backend/data/events.db` accumulates real usage.
Exports to `app/matching/artifacts/` (`vocab.json`, `weights.npz`,
`metadata.json`), which `app/matching/infer.py` loads with plain NumPy —
TensorFlow is never imported by the deployed API.
