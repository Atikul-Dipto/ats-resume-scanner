from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.analysis.skills_data import SKILLS
from app.analysis.profile_extractor import extract_skills


def match_keywords(resume_text: str, job_description: str | None) -> dict:
    resume_skills = set(extract_skills(resume_text))

    if not job_description or not job_description.strip():
        # No JD supplied: score keyword richness against a broad skills baseline.
        baseline = 15
        score = min(len(resume_skills) / baseline, 1.0) * 100
        return {
            "matched": sorted(resume_skills),
            "missing": [],
            "match_score": round(score, 1),
        }

    jd_skills = set(extract_skills(job_description))
    matched = sorted(resume_skills & jd_skills)
    missing = sorted(jd_skills - resume_skills)

    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        matrix = vectorizer.fit_transform([resume_text, job_description])
        similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
    except ValueError:
        similarity = 0.0

    skill_overlap = len(matched) / len(jd_skills) if jd_skills else 0.0
    score = (0.5 * similarity + 0.5 * skill_overlap) * 100

    return {
        "matched": matched,
        "missing": missing,
        "match_score": round(score, 1),
    }
