"""Work Signal: market signals computed from the open-jobs catalog."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.db.models import Job
from app.db.session import get_session_factory
from app.jobs.market import compute_market
from tests.test_assistant import chat, enabled, msg, text, tool, use  # noqa: F401 (fixtures)
from tests.test_job_board import ADMIN, job_payload


@pytest.fixture
def catalog(client, register):
    headers = register(ADMIN)
    jobs = [
        job_payload(title="Data Analyst", company="bKash", skills=["SQL", "Power BI"], salary_min=60000, salary_max=80000),
        job_payload(title="BI Analyst", company="bKash", skills=["SQL", "Tableau"], salary_min=70000, salary_max=90000),
        job_payload(title="Data Engineer", company="Pathao", workplace="remote", location="Remote",
                    skills=["SQL", "Python"], salary_min=1200000, salary_max=1200000, salary_period="year"),
        job_payload(title="Site Engineer", company="BuildCo", discipline="civil", location="Chattogram, Bangladesh",
                    skills=["AutoCAD"], salary_min=None, salary_max=None,
                    description="Supervise RCC construction and prepare BOQ estimates for sites."),
        job_payload(title="Closed Analyst", company="Old Co", status="closed", skills=["SQL"]),
    ]
    ids = []
    for payload in jobs:
        resp = client.post("/api/admin/jobs", json=payload, headers=headers)
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])
    return ids


def test_market_counts_open_jobs(client, catalog):
    m = client.get("/api/market").json()
    t = m["totals"]
    assert (t["open_jobs"], t["companies"], t["remote_jobs"], t["new_7d"]) == (4, 3, 1, 4)
    assert t["local_jobs"] == 3  # Dhaka x2 + Chattogram; the remote one isn't counted as local
    skills = {s["name"]: s["count"] for s in m["skills"]}
    assert skills["sql"] == 3 and skills["autocad"] == 1  # the closed job's SQL isn't counted
    assert m["companies"][0] == {"name": "bKash", "count": 2}
    assert {d["key"]: d["count"] for d in m["disciplines"]}["civil"] == 1
    assert {w["key"]: w["count"] for w in m["workplaces"]} == {"onsite": 3, "hybrid": 0, "remote": 1}
    assert sum(w["count"] for w in m["weekly_new"]) == 4 and len(m["weekly_new"]) == 8
    # Yearly salary is converted to monthly: midpoints 70k, 80k, 100k.
    assert m["salary"]["samples"] == 3 and m["salary"]["median"] == 80000
    assert m["salary"]["by_discipline"] == [{"key": "data", "median": 80000, "samples": 3}]
    assert len(m["latest"]) == 4 and all(j["status"] == "published" for j in m["latest"])


def test_market_filters(client, catalog):
    m = client.get("/api/market", params={"discipline": "civil"}).json()
    assert m["totals"]["open_jobs"] == 1 and m["salary"]["median"] is None
    m = client.get("/api/market", params={"workplace": "remote"}).json()
    assert [j["company"] for j in m["latest"]] == ["Pathao"]
    assert client.get("/api/market", params={"discipline": "bogus"}).status_code == 422


def test_skill_trend_compares_fortnights(client, catalog):
    old = datetime.now(UTC) - timedelta(days=20)
    with get_session_factory()() as db:
        db.execute(update(Job).where(Job.id == catalog[0]).values(created_at=old))
        db.commit()
        m = compute_market(db)
    sql = next(s for s in m["skills"] if s["name"] == "sql")
    assert (sql["recent"], sql["previous"]) == (2, 1)
    assert m["totals"]["new_7d"] == 3


def test_empty_market(client):
    m = client.get("/api/market").json()
    assert m["totals"]["open_jobs"] == 0 and m["skills"] == [] and m["salary"]["median"] is None


def test_jobs_filter_by_skill_links_back_to_postings(client, catalog, sample_document):
    listed = client.get("/api/jobs", params={"skill": "AutoCAD"}).json()
    assert [j["title"] for j in listed["items"]] == ["Site Engineer"] and listed["facets"] == {"civil": 1}
    # Whole-entry match: "sql" must not match a skill that merely contains it.
    assert client.get("/api/jobs", params={"skill": "sq"}).json()["total"] == 0
    matched = client.post("/api/jobs/match", json={"document": sample_document, "skill": "python"}).json()
    assert [r["job"]["title"] for r in matched["results"]] == ["Data Engineer"]


def test_assistant_market_tool(client, enabled, catalog):  # noqa: F811
    fake = use(msg(tool("market_signal", {"discipline": "data"})), msg(text("SQL leads.")))
    chat(client, "What skills are in demand?", context={"page": "market"})
    result = fake.calls[1]["messages"][-1]["content"][0]
    assert not result["is_error"]
    assert "sql 3" in result["content"] and "bKash (2)" in result["content"]
    assert "Median salary: BDT 80,000/month from 3 postings" in result["content"]


# ---------- Official indicators (World Bank WDI) ----------

def wdi(rows):
    return [{"page": 1, "pages": 1, "per_page": 8, "total": len(rows)}, rows]


def test_parse_indicator_takes_latest_reported_year():
    from app.jobs.indicators import parse

    payload = wdi([
        {"date": "2024", "value": None},
        {"date": "2023", "value": 5.06},
        {"date": "2022", "value": 4.98},
        {"date": "2021", "value": 5.2},
    ])
    item = parse("SL.UEM.TOTL.ZS", "Unemployment rate", "%", payload)
    assert (item["year"], item["value"]) == (2023, 5.1)
    assert item["previous"] == {"year": 2022, "value": 5.0}
    assert [p["year"] for p in item["series"]] == [2021, 2022, 2023]
    assert parse("x", "x", "%", [{"message": [{"id": "120", "value": "Invalid value"}]}]) is None
    assert parse("x", "x", "%", wdi([{"date": "2023", "value": None}])) is None


def test_indicators_endpoint_fetches_once_and_caches(client):
    import httpx

    from app.jobs import indicators

    calls = []

    def handler(request):
        calls.append(str(request.url))
        if "SL.UEM.1524.ZS" in str(request.url):
            return httpx.Response(500)
        return httpx.Response(200, json=wdi([{"date": "2023", "value": 12.5}, {"date": "2022", "value": 11.0}]))

    client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    data = client.get("/api/market/indicators").json()
    assert data["available"] and data["source"]["license"] == "CC BY 4.0"
    assert len(data["indicators"]) == len(indicators.INDICATORS) - 1  # the failed one is skipped
    assert data["indicators"][0]["value"] == 12.5
    first = len(calls)
    client.get("/api/market/indicators")
    assert len(calls) == first  # served from cache


def test_indicators_unavailable(client):
    import httpx

    client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    assert client.get("/api/market/indicators").json() == {
        "available": False,
        "source": client.get("/api/market/indicators").json()["source"],
        "indicators": [],
    }
