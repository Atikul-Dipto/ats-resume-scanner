import numpy as np

from app.matching.infer import cosine_similarity, get_encoder
from app.matching.store import (
    event_count,
    fetch_events,
    fetch_resume_scans,
    log_event,
    log_resume_scan,
    resume_scan_count,
)


def test_encoder_loads_from_committed_artifacts():
    encoder = get_encoder()
    assert encoder is not None


def test_encoder_embeddings_are_unit_length():
    encoder = get_encoder()
    vec = encoder.embed("Data Analyst skills: python, sql")
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-5


def test_encoder_ranks_related_role_above_unrelated_role():
    encoder = get_encoder()
    candidate = encoder.embed("Data Analyst skills: python, sql, power bi")
    related = encoder.embed("Business Intelligence Analyst. SQL and Power BI reporting role.")
    unrelated = encoder.embed("Truck Driver. CDL required, long haul routes.")

    assert cosine_similarity(candidate, related) > cosine_similarity(candidate, unrelated)


def test_embed_batch_matches_single_embed():
    encoder = get_encoder()
    texts = ["Data Analyst", "Software Engineer"]
    batch = encoder.embed_batch(texts)
    singles = np.stack([encoder.embed(t) for t in texts])
    assert np.allclose(batch, singles, atol=1e-6)


def test_log_event_and_fetch_events_roundtrip():
    assert event_count() == 0

    log_event(
        resume_title="Data Analyst",
        skills=["python", "sql"],
        years_experience=3.0,
        job_title="Data Analyst",
        job_company="Acme",
        job_source="Remotive",
        relevance_score=88.0,
    )

    events = fetch_events()
    assert len(events) == 1
    assert events[0]["skills"] == ["python", "sql"]
    assert events[0]["job_company"] == "Acme"
    assert event_count() == 1


def test_log_resume_scan_and_fetch_roundtrip():
    assert resume_scan_count() == 0

    log_resume_scan(
        title="Data Analyst",
        skills=["python", "sql"],
        years_experience=4.0,
        ats_score=78.0,
        formatting_score=100.0,
        content_score=67.0,
        keyword_score=36.2,
        had_job_description=True,
    )

    scans = fetch_resume_scans()
    assert len(scans) == 1
    assert scans[0]["title"] == "Data Analyst"
    assert scans[0]["skills"] == ["python", "sql"]
    assert scans[0]["ats_score"] == 78.0
    assert scans[0]["had_job_description"] is True
    assert resume_scan_count() == 1


def test_resume_scan_and_match_event_tables_are_independent():
    log_resume_scan(
        title="Data Analyst",
        skills=["python"],
        years_experience=None,
        ats_score=50.0,
        formatting_score=50.0,
        content_score=50.0,
        keyword_score=50.0,
        had_job_description=False,
    )

    assert resume_scan_count() == 1
    assert event_count() == 0
