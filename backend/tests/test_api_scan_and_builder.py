import json

from app.builder.export_docx import render_docx
from app.builder.export_pdf import render_pdf
from app.matching.store import fetch_resume_scans
from app.parsers.pdf_parser import parse_pdf
from app.schemas.resume import ResumeDocument


def _pdf(sample_document) -> bytes:
    return render_pdf(ResumeDocument.model_validate(sample_document))


# --- builder ------------------------------------------------------------

def test_builder_score_endpoint(client, sample_document):
    resp = client.post("/api/builder/score", json={
        "document": sample_document,
        "job_description": "Data analyst with Python, SQL and Snowflake.",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert 0 < body["ats_score"] <= 100
    assert "snowflake" in body["keywords"]["missing"]
    assert body["profile"]["current_title"] == "Data Analyst"


def test_builder_score_on_empty_document_is_low_but_valid(client):
    resp = client.post("/api/builder/score", json={"document": {}})
    assert resp.status_code == 200
    assert resp.json()["ats_score"] < 40
    assert any(i["severity"] == "critical" for i in resp.json()["formatting_issues"])


def test_builder_validation_errors_are_422(client):
    resp = client.post("/api/builder/score", json={"document": {"experience": [{"start": "last spring"}]}})
    assert resp.status_code == 422


def test_export_pdf_and_docx(client, sample_document):
    pdf = client.post("/api/builder/export/pdf", json={"document": sample_document})
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert 'filename="Jane_Doe_Resume.pdf"' in pdf.headers["content-disposition"]
    assert "Jane Doe" in parse_pdf(pdf.content)["text"]

    docx = client.post("/api/builder/export/docx", json={"document": sample_document, "filename": "../../etc/passwd"})
    assert docx.status_code == 200
    assert docx.content.startswith(b"PK")
    assert 'filename="etc_passwd.docx"' in docx.headers["content-disposition"]  # sanitized

    assert client.post("/api/builder/export/exe", json={"document": sample_document}).status_code == 422


# --- upload scan --------------------------------------------------------

def test_analyze_pdf_returns_analysis_and_builder_draft(client, sample_document):
    resp = client.post(
        "/api/analyze",
        files={"file": ("resume.pdf", _pdf(sample_document), "application/pdf")},
        data={"job_description": "Python SQL Tableau analyst"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["formatting_issues"] == []
    assert "python" in body["keywords"]["matched"]
    draft = body["draft_document"]
    assert draft["basics"]["name"] == "Jane Doe"
    assert draft["experience"][0]["title"] == "Data Analyst"
    assert resp.headers["x-request-id"]


def test_analyze_docx(client, sample_document):
    content = render_docx(ResumeDocument.model_validate(sample_document))
    resp = client.post("/api/analyze", files={"file": ("resume.docx", content, "application/octet-stream")})
    assert resp.status_code == 200
    assert resp.json()["content_score"] == 100


def test_analyze_rejects_bad_uploads(client, monkeypatch, sample_document):
    from app.core.config import get_settings

    assert client.post("/api/analyze", files={"file": ("r.txt", b"hello", "text/plain")}).status_code == 400
    assert client.post("/api/analyze", files={"file": ("r.pdf", b"PK\x03\x04zip", "application/pdf")}).status_code == 400
    assert client.post("/api/analyze", files={"file": ("r.pdf", b"%PDF-1.4 garbage", "application/pdf")}).status_code == 422

    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()
    assert client.post("/api/analyze", files={"file": ("r.pdf", _pdf(sample_document), "application/pdf")}).status_code == 413

    monkeypatch.setenv("MAX_UPLOAD_MB", "5")
    monkeypatch.setenv("MAX_PDF_PAGES", "0")
    get_settings.cache_clear()
    resp = client.post("/api/analyze", files={"file": ("r.pdf", _pdf(sample_document), "application/pdf")})
    assert resp.status_code == 413
    assert "limit is 0" in resp.json()["detail"]


def test_analyze_logs_only_anonymized_event(client, sample_document):
    client.post("/api/analyze", files={"file": ("resume.pdf", _pdf(sample_document), "application/pdf")})
    events = fetch_resume_scans()
    assert len(events) == 1
    stored = json.dumps(events[0])
    assert "jane@example.com" not in stored
    assert "415-555" not in stored
    assert "Jane Doe" not in stored
    assert events[0]["title"] == "Data Analyst"


def test_signed_in_upload_lands_in_scan_history(client, register, sample_document):
    from app.db.models import Scan
    from app.db.session import get_session_factory

    headers = register()
    client.post("/api/analyze", headers=headers, files={"file": ("cv.pdf", _pdf(sample_document), "application/pdf")})
    with get_session_factory()() as db:
        scans = db.query(Scan).all()
    assert len(scans) == 1
    assert scans[0].source == "upload" and scans[0].filename == "cv.pdf"


def test_analyze_rate_limit_returns_retry_after(client, monkeypatch, sample_document):
    from app.core.config import get_settings

    monkeypatch.setenv("RATE_LIMIT_ANALYZE", "1/minute")
    get_settings.cache_clear()
    files = {"file": ("r.pdf", _pdf(sample_document), "application/pdf")}
    assert client.post("/api/analyze", files=files).status_code == 200
    limited = client.post("/api/analyze", files=files)
    assert limited.status_code == 429
    assert 0 < int(limited.headers["retry-after"]) <= 60


# --- ops ----------------------------------------------------------------

def test_health_ready_stats(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    ready = client.get("/api/ready")
    assert ready.status_code == 200 and ready.json()["checks"] == {"database": True, "cache": True}
    assert client.get("/api/stats").json() == {
        "resume_scans": 0, "job_search_events": 0, "open_jobs": 0, "companies_hiring": 0, "local_jobs": 0,
    }


def test_meta_reports_storage_and_admin(client, monkeypatch):
    from app.core.config import get_settings

    assert client.get("/api/meta").json() == {"persistent_storage": True, "admin_configured": True}

    # /api/meta only reads settings, so the URL can point anywhere here.
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("ADMIN_EMAILS", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/unused.db")
    get_settings.cache_clear()
    assert client.get("/api/meta").json() == {"persistent_storage": False, "admin_configured": False}

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example/ats")
    get_settings.cache_clear()
    assert client.get("/api/meta").json()["persistent_storage"] is True


def test_cors_allows_configured_origin_only(client):
    ok = client.options("/api/builder/score", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    blocked = client.options("/api/builder/score", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST",
    })
    assert "access-control-allow-origin" not in blocked.headers


def test_unhandled_errors_return_json_with_request_id(client, monkeypatch, sample_document):
    def boom(*_args, **_kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("app.api.routes.builder.analyze_document", boom)
    resp = client.post("/api/builder/score", json={"document": sample_document},
                       headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 500
    assert resp.json()["request_id"] == resp.headers["x-request-id"]
    assert "kaboom" not in resp.text
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
