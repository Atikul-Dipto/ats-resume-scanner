import asyncio
import copy
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from app.jobs import catalog_sync
from app.jobs.catalog_sync import html_to_text, sync_external_jobs, upsert_external
from app.jobs.taxonomy import classify_profile, classify_title

ADMIN = "admin@example.com"


def job_payload(**overrides) -> dict:
    payload = {
        "title": "Data Analyst",
        "company": "Acme Bangladesh Ltd",
        "location": "Dhaka",
        "discipline": "data",
        "employment_type": "full_time",
        "workplace": "onsite",
        "experience_min": 2,
        "salary_min": 50000,
        "salary_max": 80000,
        "description": "Build dashboards in Power BI and Tableau, write SQL against our warehouse, "
                       "and present insights to stakeholders.",
        "skills": ["Power BI", "SQL", "Excel"],
        "apply_url": "https://acme.example/careers/123",
    }
    return {**payload, **overrides}


CATALOG = [
    job_payload(),
    job_payload(title="Civil Site Engineer", company="BuildCo", discipline="civil", experience_min=3,
                description="Supervise RCC construction sites, prepare BOQ and estimation, model in STAAD Pro and AutoCAD.",
                skills=["AutoCAD", "STAAD Pro", "Estimation"]),
    job_payload(title="Electrical Engineer (Substation)", company="PowerGrid", discipline="electrical",
                description="Design and maintain 33/11 kV substations, ETAP load flow studies, PLC and SCADA integration.",
                skills=["ETAP", "PLC", "SCADA"]),
    job_payload(title="Frontend Developer", company="SoftHouse", discipline="software", workplace="remote",
                description="Build React and TypeScript interfaces, write Jest tests, work with Node.js APIs.",
                skills=["React", "TypeScript", "Node.js"]),
    job_payload(title="Merchandiser (Knit)", company="RMG Group", discipline="mechanical",
                description="Handle knitting and dyeing orders, buyer communication, production planning, line balancing.",
                skills=["Merchandising", "Knitting", "Production planning"]),
]

CIVIL_RESUME = {
    "basics": {"name": "Rahim Uddin", "email": "rahim@example.com", "headline": "Civil Engineer"},
    "experience": [{
        "title": "Site Engineer", "company": "Concord", "start": "2019-01", "current": True,
        "bullets": ["Supervised RCC construction of 12-storey buildings, prepared BOQ and estimation for 3 projects.",
                    "Modeled structures in STAAD Pro and drafted in AutoCAD, cutting rework by 20%."],
    }],
    "skills": [{"skills": ["AutoCAD", "STAAD Pro", "ETABS", "Estimation"]}],
}


@pytest.fixture
def admin(register):
    return register(ADMIN)


@pytest.fixture
def seeded(client, admin):
    ids = []
    for payload in CATALOG:
        resp = client.post("/api/admin/jobs", headers=admin, json=payload)
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])
    return ids


# --- taxonomy -----------------------------------------------------------

@pytest.mark.parametrize("title,expected", [
    ("Data Engineer", "data"),
    ("Senior Business Analyst", "data"),
    ("MIS Executive", "data"),
    ("Civil Engineer (Site)", "civil"),
    ("Quantity Surveyor", "civil"),
    ("Electrical Maintenance Engineer", "electrical"),
    ("PLC Programmer", "electrical"),
    ("IE Executive", "mechanical"),
    ("Merchandiser - Knit", "mechanical"),
    ("SQA Engineer", "software"),
    ("Full-Stack Developer", "software"),
    ("Sales Manager", None),
    ("Customer Support Agent", None),
    ("Product Manager", None),
])
def test_classify_title(title, expected):
    assert classify_title(title) == expected


def test_classify_profile_uses_skills_when_title_is_vague():
    assert classify_profile("Engineer", ["autocad", "staad pro", "etabs", "estimation"]) == "civil"
    assert classify_profile(None, ["python", "sql", "power bi", "tableau"]) == "data"
    assert classify_profile("Data Analyst", ["python"]) == "data"
    assert classify_profile(None, ["excel"]) is None


def test_html_to_text_keeps_structure_and_drops_markup():
    text = html_to_text("<p>We need:</p><ul><li>SQL &amp; Python</li><li>Power BI</li></ul><script>x</script>")
    assert text == "We need:\n• SQL & Python\n• Power BI\nx"


# --- admin --------------------------------------------------------------

def test_only_admins_can_manage_jobs(client, register):
    user = register("someone@example.com")
    assert client.post("/api/admin/jobs", json=job_payload()).status_code == 401
    assert client.post("/api/admin/jobs", headers=user, json=job_payload()).status_code == 403
    assert client.get("/api/admin/jobs", headers=user).status_code == 403
    assert client.post("/api/admin/jobs/sync", headers=user).status_code == 403

    admin = register(ADMIN)
    assert client.get("/api/auth/me", headers=admin).json()["is_admin"] is True
    assert client.get("/api/auth/me", headers=user).json()["is_admin"] is False


def test_admin_create_normalizes_skills(client, admin):
    resp = client.post("/api/admin/jobs", headers=admin, json=job_payload())
    assert resp.status_code == 201
    skills = resp.json()["skills"]
    assert skills[:3] == ["power bi", "sql", "excel"]  # admin's list first, lowercased
    assert "tableau" in skills  # mentioned in the description


@pytest.mark.parametrize("bad", [
    {"apply_url": "javascript:alert(1)"},
    {"apply_url": "data:text/html,<script>alert(1)</script>"},
    {"salary_min": 90000, "salary_max": 1000},
    {"experience_min": 5, "experience_max": 2},
    {"discipline": "medicine"},
    {"description": "too short"},
])
def test_admin_job_validation(client, admin, bad):
    assert client.post("/api/admin/jobs", headers=admin, json=job_payload(**bad)).status_code == 422


def test_admin_update_close_delete(client, admin):
    job_id = client.post("/api/admin/jobs", headers=admin, json=job_payload()).json()["id"]
    updated = client.put(f"/api/admin/jobs/{job_id}", headers=admin, json=job_payload(title="Senior Data Analyst"))
    assert updated.json()["title"] == "Senior Data Analyst"

    assert client.get(f"/api/jobs/{job_id}").status_code == 200
    client.post(f"/api/admin/jobs/{job_id}/status", headers=admin, json={"status": "closed"})
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get("/api/jobs").json()["total"] == 0

    assert client.delete(f"/api/admin/jobs/{job_id}", headers=admin).status_code == 204
    assert client.get(f"/api/admin/jobs/{job_id}", headers=admin).status_code == 404


# --- public catalog -----------------------------------------------------

def test_list_filters_facets_and_visibility(client, admin, seeded):
    client.post("/api/admin/jobs", headers=admin, json=job_payload(title="Draft Analyst", status="draft"))
    client.post("/api/admin/jobs", headers=admin,
                json=job_payload(title="Expired Analyst", deadline=(date.today() - timedelta(days=1)).isoformat()))

    everything = client.get("/api/jobs").json()
    assert everything["total"] == len(CATALOG)  # drafts and expired listings are hidden
    assert everything["facets"] == {"data": 1, "civil": 1, "electrical": 1, "software": 1, "mechanical": 1}
    assert everything["disciplines"]["mechanical"] == "Mechanical, Industrial & Textile"

    civil = client.get("/api/jobs", params={"discipline": "civil"}).json()
    assert [j["title"] for j in civil["items"]] == ["Civil Site Engineer"]
    assert civil["facets"]["data"] == 1  # facets ignore the discipline filter, so chips keep their counts

    assert client.get("/api/jobs", params={"q": "powergrid"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"q": "100%_"}).json()["total"] == 0  # LIKE wildcards escaped
    assert client.get("/api/jobs", params={"workplace": "remote"}).json()["items"][0]["title"] == "Frontend Developer"
    assert client.get("/api/jobs", params={"discipline": "medicine"}).status_code == 422

    detail = client.get(f"/api/jobs/{seeded[0]}").json()
    assert "Power BI" in detail["description"]
    assert len(everything["items"][0]["snippet"]) <= 221


# --- matching -----------------------------------------------------------

def test_data_resume_ranks_data_job_first(client, seeded, sample_document):
    resp = client.post("/api/jobs/match", json={"document": sample_document})
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile"]["detected_discipline"] == "data"
    assert body["total_considered"] == len(CATALOG)
    top = body["results"][0]
    assert top["job"]["title"] == "Data Analyst"
    assert {"power bi", "sql", "excel", "tableau"} <= set(top["matched_skills"])
    assert top["match_score"] > body["results"][-1]["match_score"] + 20
    scores = [r["match_score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_civil_resume_ranks_civil_job_first_and_reports_gaps(client, seeded):
    body = client.post("/api/jobs/match", json={"document": CIVIL_RESUME}).json()
    assert body["profile"]["detected_discipline"] == "civil"
    top = body["results"][0]
    assert top["job"]["title"] == "Civil Site Engineer"
    assert "staad pro" in top["matched_skills"]
    electrical = next(r for r in body["results"] if r["job"]["discipline"] == "electrical")
    assert {"etap", "plc", "scada"} <= set(electrical["missing_skills"])


def test_match_filters_and_limit(client, seeded, sample_document):
    only_civil = client.post("/api/jobs/match", json={"document": sample_document, "discipline": "civil"}).json()
    assert [r["job"]["discipline"] for r in only_civil["results"]] == ["civil"]
    remote = client.post("/api/jobs/match", json={"document": sample_document, "workplace": "remote"}).json()
    assert [r["job"]["title"] for r in remote["results"]] == ["Frontend Developer"]
    limited = client.post("/api/jobs/match", json={"document": sample_document, "limit": 2}).json()
    assert len(limited["results"]) == 2 and limited["total_considered"] == len(CATALOG)


def test_experience_gap_lowers_score_and_explains(client, admin, sample_document):
    junior = client.post("/api/admin/jobs", headers=admin, json=job_payload(experience_min=1)).json()["id"]
    senior = client.post("/api/admin/jobs", headers=admin, json=job_payload(experience_min=15)).json()["id"]
    results = {r["job"]["id"]: r for r in client.post("/api/jobs/match", json={"document": sample_document}).json()["results"]}
    assert results[junior]["match_score"] > results[senior]["match_score"]
    assert results[junior]["experience_note"] is None
    assert "15+ years" in results[senior]["experience_note"]


def test_match_index_refreshes_when_catalog_changes(client, admin, sample_document):
    assert client.post("/api/jobs/match", json={"document": sample_document}).json()["results"] == []
    client.post("/api/admin/jobs", headers=admin, json=job_payload())
    assert len(client.post("/api/jobs/match", json={"document": sample_document}).json()["results"]) == 1


def test_match_with_empty_resume_is_safe(client, seeded):
    body = client.post("/api/jobs/match", json={"document": {}}).json()
    assert body["results"] == [] and body["profile"]["detected_discipline"] is None


# --- importing remote jobs ----------------------------------------------

REMOTIVE = {"jobs": [
    {"title": "Senior Data Analyst", "company_name": "Globex", "candidate_required_location": "Worldwide",
     "url": "https://remotive.example/1", "description": "<p>SQL, <b>Power BI</b> and Python.</p>"},
    {"title": "Structural Engineer", "company_name": "Arup-ish", "candidate_required_location": "Anywhere",
     "url": "https://remotive.example/2", "description": "<p>ETABS and STAAD Pro modelling.</p>"},
    {"title": "Sales Manager", "company_name": "Initech", "candidate_required_location": "Worldwide",
     "url": "https://remotive.example/3", "description": "Sell things."},
    {"title": "Data Engineer", "company_name": "Evil", "candidate_required_location": "Worldwide",
     "url": "javascript:alert(1)", "description": "x"},
]}
ARBEITNOW = {"data": [
    {"title": "Backend Developer", "company_name": "Berlin GmbH", "location": "Berlin", "remote": False,
     "tags": ["developer"], "url": "https://arbeitnow.example/1", "description": "Go and Kubernetes."},
    {"title": "Backend Developer", "company_name": "Remote GmbH", "location": "", "remote": True,
     "tags": ["developer"], "url": "https://arbeitnow.example/2", "description": "Python, Django and Docker."},
]}


def _transport():
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if "remotive" in host:
            return httpx.Response(200, json=REMOTIVE)
        if "arbeitnow" in host:
            return httpx.Response(200, json=ARBEITNOW)
        return httpx.Response(503)

    return httpx.MockTransport(handler)


def _sync():
    async def run():
        async with httpx.AsyncClient(transport=_transport()) as http:
            return await sync_external_jobs(http)

    return asyncio.run(run())


def test_sync_imports_only_remote_engineering_jobs(client):
    stats = _sync()
    assert stats["created"] == 3
    titles = sorted(j["title"] for j in client.get("/api/jobs").json()["items"])
    # Sales (not engineering), javascript: link and the on-site Berlin job are all dropped.
    assert titles == ["Backend Developer", "Senior Data Analyst", "Structural Engineer"]
    imported = client.get("/api/jobs", params={"discipline": "civil"}).json()["items"][0]
    assert imported["source"] == "remotive" and imported["workplace"] == "remote"
    assert {"etabs", "staad pro"} <= set(imported["skills"])
    assert "<b>" not in client.get(f"/api/jobs/{imported['id']}").json()["description"]


def test_resync_updates_in_place_and_respects_hidden_jobs(client, admin):
    _sync()
    job = client.get("/api/jobs", params={"discipline": "data"}).json()["items"][0]
    client.post(f"/api/admin/jobs/{job['id']}/status", headers=admin, json={"status": "closed"})

    stats = _sync()
    assert stats["created"] == 0 and stats["updated"] == 3
    assert client.get("/api/jobs").json()["total"] == 2  # still hidden after re-import
    assert client.put(f"/api/admin/jobs/{job['id']}", headers=admin, json=job_payload()).status_code == 409
    assert client.delete(f"/api/admin/jobs/{job['id']}", headers=admin).status_code == 409


def test_imported_jobs_age_out(client):
    _sync()
    future = datetime.now(UTC) + timedelta(days=40)
    stats = upsert_external([], now=future)
    assert stats["expired"] == 3
    assert client.get("/api/jobs").json()["total"] == 0


def test_background_sync_runs_once_when_stale(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("JOBS_SYNC_ENABLED", "true")
    get_settings.cache_clear()
    calls = []

    async def fake_sync(_client):
        calls.append(1)
        return {}

    monkeypatch.setattr(catalog_sync, "sync_external_jobs", fake_sync)

    async def scenario():
        first = await catalog_sync.maybe_schedule_sync(None)
        second = await catalog_sync.maybe_schedule_sync(None)
        await asyncio.sleep(0)
        return first, second

    assert asyncio.run(scenario()) == (True, False)  # lock prevents a stampede
    assert calls == [1]


def test_background_sync_skipped_when_fresh(monkeypatch):
    from app.core.config import get_settings

    _sync()  # catalog now has recently-seen imported jobs
    monkeypatch.setenv("JOBS_SYNC_ENABLED", "true")
    get_settings.cache_clear()
    assert asyncio.run(catalog_sync.maybe_schedule_sync(None)) is False


def test_match_is_rate_limited(client, monkeypatch, sample_document):
    from app.core.config import get_settings

    monkeypatch.setenv("RATE_LIMIT_MATCH", "2/minute")
    get_settings.cache_clear()
    payload = {"document": copy.deepcopy(sample_document)}
    codes = [client.post("/api/jobs/match", json=payload).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
