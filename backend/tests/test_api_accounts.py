from sqlalchemy import func, select

from app.db.models import Resume, Scan
from app.db.session import get_session_factory


def _count(model) -> int:
    with get_session_factory()() as db:
        return db.scalar(select(func.count()).select_from(model))


# --- auth ---------------------------------------------------------------

def test_register_login_me(client):
    resp = client.post("/api/auth/register", json={"email": "Jane@Example.com", "password": "correct-horse"})
    assert resp.status_code == 201
    assert resp.json()["user"]["email"] == "jane@example.com"  # normalized

    resp = client.post("/api/auth/login", json={"email": "JANE@example.com", "password": "correct-horse"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "jane@example.com"
    assert "password_hash" not in me.json()


def test_register_rejects_duplicates_and_weak_input(client, register):
    register()
    assert client.post("/api/auth/register", json={"email": "jane@example.com", "password": "another-pass"}).status_code == 409
    assert client.post("/api/auth/register", json={"email": "not-an-email", "password": "long-enough"}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422


def test_login_failures_are_indistinguishable(client, register):
    register()
    wrong_password = client.post("/api/auth/login", json={"email": "jane@example.com", "password": "wrong-password"})
    unknown_email = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_invalid_token_is_401_not_anonymous(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    # Even on endpoints that allow anonymous use, a bad token is surfaced.
    resp = client.post("/api/analyze", headers={"Authorization": "Bearer nonsense"},
                       files={"file": ("r.pdf", b"%PDF-1.4", "application/pdf")})
    assert resp.status_code == 401


def test_auth_endpoints_are_rate_limited(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("RATE_LIMIT_AUTH", "3/minute")
    get_settings.cache_clear()
    codes = [
        client.post("/api/auth/login", json={"email": "x@example.com", "password": "whatever-123"}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]


def test_delete_account_removes_all_owned_data(client, register, sample_document):
    headers = register()
    created = client.post("/api/resumes", headers=headers, json={"title": "Main", "document": sample_document})
    assert created.status_code == 201
    assert _count(Resume) == 1 and _count(Scan) == 1

    assert client.delete("/api/auth/me", headers=headers).status_code == 204
    assert _count(Resume) == 0 and _count(Scan) == 0
    assert client.get("/api/auth/me", headers=headers).status_code == 401


# --- resumes ------------------------------------------------------------

def test_resume_crud_flow(client, register, sample_document):
    headers = register()
    assert client.get("/api/resumes", headers=headers).json() == []

    created = client.post("/api/resumes", headers=headers, json={"title": "Data roles", "document": sample_document})
    assert created.status_code == 201
    body = created.json()
    assert body["version"] == 1
    assert body["last_score"] > 0
    resume_id = body["id"]

    sample_document["basics"]["headline"] = "Senior Data Analyst"
    updated = client.put(f"/api/resumes/{resume_id}", headers=headers, json={
        "title": "Data roles v2", "document": sample_document, "version": 1,
        "target_job_description": "Data analyst with SQL and Snowflake",
    })
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["document"]["basics"]["headline"] == "Senior Data Analyst"

    listing = client.get("/api/resumes", headers=headers).json()
    assert [r["title"] for r in listing] == ["Data roles v2"]
    assert "document" not in listing[0]  # summaries stay small

    dup = client.post(f"/api/resumes/{resume_id}/duplicate", headers=headers)
    assert dup.status_code == 201 and dup.json()["title"] == "Data roles v2 (copy)"

    assert client.delete(f"/api/resumes/{resume_id}", headers=headers).status_code == 204
    assert client.get(f"/api/resumes/{resume_id}", headers=headers).status_code == 404


def test_stale_version_is_rejected(client, register, sample_document):
    headers = register()
    resume_id = client.post("/api/resumes", headers=headers, json={"title": "R", "document": sample_document}).json()["id"]
    payload = {"title": "R", "document": sample_document, "version": 1}

    assert client.put(f"/api/resumes/{resume_id}", headers=headers, json=payload).status_code == 200
    # Second tab still thinks it's editing version 1.
    conflict = client.put(f"/api/resumes/{resume_id}", headers=headers, json=payload)
    assert conflict.status_code == 409
    assert client.get(f"/api/resumes/{resume_id}", headers=headers).json()["version"] == 2


def test_users_cannot_see_or_touch_each_others_resumes(client, register, sample_document):
    alice = register("alice@example.com")
    bob = register("bob@example.com")
    resume_id = client.post("/api/resumes", headers=alice, json={"title": "Alice", "document": sample_document}).json()["id"]

    assert client.get("/api/resumes", headers=bob).json() == []
    assert client.get(f"/api/resumes/{resume_id}", headers=bob).status_code == 404
    assert client.put(f"/api/resumes/{resume_id}", headers=bob,
                      json={"title": "x", "document": sample_document, "version": 1}).status_code == 404
    assert client.delete(f"/api/resumes/{resume_id}", headers=bob).status_code == 404
    assert client.get(f"/api/resumes/{resume_id}/scans", headers=bob).status_code == 404
    assert client.get(f"/api/resumes/{resume_id}", headers=alice).status_code == 200


def test_resumes_require_auth(client, sample_document):
    assert client.get("/api/resumes").status_code == 401
    assert client.post("/api/resumes", json={"title": "x", "document": sample_document}).status_code == 401


def test_resume_quota(client, register, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("MAX_RESUMES_PER_USER", "2")
    get_settings.cache_clear()
    headers = register()
    for i in range(2):
        assert client.post("/api/resumes", headers=headers, json={"title": f"R{i}"}).status_code == 201
    assert client.post("/api/resumes", headers=headers, json={"title": "R3"}).status_code == 409


def test_score_history_records_changes_only(client, register, sample_document):
    headers = register()
    resume_id = client.post("/api/resumes", headers=headers, json={"title": "R", "document": sample_document}).json()["id"]

    same = {"title": "R renamed", "document": sample_document, "version": 1}
    client.put(f"/api/resumes/{resume_id}", headers=headers, json=same)
    assert len(client.get(f"/api/resumes/{resume_id}/scans", headers=headers).json()) == 1

    sample_document["experience"][1]["bullets"] = []
    client.put(f"/api/resumes/{resume_id}", headers=headers, json={**same, "document": sample_document, "version": 2})
    history = client.get(f"/api/resumes/{resume_id}/scans", headers=headers).json()
    assert len(history) == 2
    assert all(scan["source"] == "builder" for scan in history)
