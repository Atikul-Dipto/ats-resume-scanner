import asyncio

import httpx

from app.core.cache import MemoryCache
from app.jobs import sources
from app.matching.store import fetch_events

REMOTIVE_JOBS = {
    "jobs": [
        {"title": "Data Analyst", "company_name": "Acme", "candidate_required_location": "Worldwide",
         "url": "https://remotive.example/1", "description": "SQL, Python and Power BI dashboards."},
        {"title": "Truck Driver", "company_name": "Haulers", "candidate_required_location": "USA",
         "url": "https://remotive.example/2", "description": "CDL required, long haul."},
    ]
}
ARBEITNOW_FEED = {
    "data": [
        {"title": "BI Analyst", "company_name": "Beta", "location": "Berlin", "tags": ["sql"],
         "url": "https://arbeitnow.example/1", "description": "Tableau and SQL reporting."},
        {"title": "Chef", "company_name": "Kitchen", "location": "Berlin", "tags": [],
         "url": "https://arbeitnow.example/2", "description": "Cooking."},
    ]
}


def _transport(calls: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        calls[host] = calls.get(host, 0) + 1
        if "remotive" in host:
            return httpx.Response(200, json=REMOTIVE_JOBS)
        if "arbeitnow" in host:
            return httpx.Response(200, json=ARBEITNOW_FEED)
        if "themuse" in host:
            return httpx.Response(503)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_job_search_ranks_filters_and_survives_a_failing_provider(client):
    calls: dict = {}
    client.app.state.http = httpx.AsyncClient(transport=_transport(calls))

    resp = client.post("/api/jobs/search", data={"query": "Data Analyst", "skills": "sql,python"})
    assert resp.status_code == 200
    titles = [job["title"] for job in resp.json()["results"]]
    assert titles[0] == "Data Analyst"
    assert "BI Analyst" in titles
    assert "Truck Driver" not in titles  # zero overlap is dropped
    assert "Chef" not in titles
    assert calls["www.themuse.com"] == 1  # it failed, and the search still answered


def test_job_search_is_cached_across_requests(client):
    calls: dict = {}
    client.app.state.http = httpx.AsyncClient(transport=_transport(calls))

    for query in ("Data Analyst", "data   analyst", "SQL Analyst"):
        assert client.post("/api/jobs/search", data={"query": query}).status_code == 200

    assert calls["remotive.com"] == 2  # "Data Analyst" and its normalized twin share one entry
    assert calls["www.arbeitnow.com"] == 1  # whole feed fetched once, filtered per query


def test_job_search_logs_anonymized_match_events(client):
    client.app.state.http = httpx.AsyncClient(transport=_transport({}))
    client.post("/api/jobs/search", data={"query": "Data Analyst", "skills": "sql"})
    events = fetch_events()
    assert 1 <= len(events) <= 3
    assert events[-1]["resume_title"] == "Data Analyst"


def test_failed_provider_responses_are_not_cached():
    calls: dict = {}
    cache = MemoryCache()

    async def scenario():
        async with httpx.AsyncClient(transport=_transport(calls)) as http:
            await sources.fetch_themuse(http, "analyst", cache)
            await sources.fetch_themuse(http, "analyst", cache)

    asyncio.run(scenario())
    assert calls["www.themuse.com"] == 2


def test_job_search_validates_input(client):
    assert client.post("/api/jobs/search", data={"query": ""}).status_code == 422
    assert client.post("/api/jobs/search", data={"query": "x" * 201}).status_code == 422
