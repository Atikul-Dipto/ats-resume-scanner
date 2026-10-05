import asyncio
import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from app.ingest import http as ingest_http
from app.ingest.http import USER_AGENT, PoliteClient
from app.ingest.jsonld import postings_from_html
from app.ingest.models import IngestConfig, Posting, SourceConfig
from app.ingest.pipeline import save, triage
from app.ingest.run import load_config, run


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Throttling is tested by recording sleeps, not by waiting for them."""
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(ingest_http.asyncio, "sleep", fake_sleep)
    return slept


def jsonld_page(*nodes, wrap_graph=False) -> str:
    data = {"@context": "https://schema.org", "@graph": list(nodes)} if wrap_graph else list(nodes)
    return f'<html><head><script type="application/ld+json">{json.dumps(data)}</script></head><body>x</body></html>'


JOB_NODE = {
    "@type": "JobPosting",
    "title": "Data Analyst",
    "hiringOrganization": {"@type": "Organization", "name": "Acme BD"},
    "jobLocation": {"@type": "Place", "address": {"addressLocality": "Dhaka", "addressCountry": "BD"}},
    "employmentType": ["FULL_TIME"],
    "validThrough": "2099-01-31T23:59",
    "description": "<p>SQL, <b>Power BI</b> and Python.</p>",
    "baseSalary": {"@type": "MonetaryAmount", "currency": "BDT",
                   "value": {"@type": "QuantitativeValue", "minValue": 50000, "maxValue": 80000, "unitText": "MONTH"}},
}


def mock_http(routes: dict[str, httpx.Response | dict | list | str], calls: list | None = None) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        url = str(request.url)
        for prefix, response in routes.items():
            if url.startswith(prefix):
                if isinstance(response, httpx.Response):
                    return response
                if isinstance(response, str):
                    return httpx.Response(200, text=response)
                return httpx.Response(200, json=response)
        return httpx.Response(404, text="not found")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def config(*sources: dict, **overrides) -> IngestConfig:
    return IngestConfig.model_validate({"min_delay_seconds": 0.5, "sources": list(sources), **overrides})


# --- JSON-LD ------------------------------------------------------------

def test_jsonld_extracts_full_posting():
    [p] = postings_from_html(jsonld_page(JOB_NODE), "https://acme.example/jobs/1")
    assert p.title == "Data Analyst" and p.company == "Acme BD"
    assert p.location == "Dhaka, BD"
    assert p.url == "https://acme.example/jobs/1"
    assert p.employment_type == "full_time"
    assert p.deadline == date(2099, 1, 31)
    assert (p.salary_min, p.salary_max, p.salary_currency, p.salary_period) == (50000, 80000, "BDT", "month")
    assert "Power BI" in p.description and "<b>" not in p.description


def test_jsonld_handles_graph_remote_and_ignores_other_types():
    remote = {**JOB_NODE, "title": "Remote Data Engineer", "jobLocationType": "TELECOMMUTE", "url": "https://x.example/9"}
    html = jsonld_page({"@type": "Organization", "name": "Acme"}, remote, wrap_graph=True)
    [p] = postings_from_html(html, "https://fallback.example")
    assert p.remote is True and p.url == "https://x.example/9"
    assert postings_from_html("<script type='application/ld+json'>{not json</script>", "u") == []


# --- robots.txt & politeness ---------------------------------------------

def test_robots_disallow_is_honoured_and_user_agent_is_honest():
    calls = []
    http = mock_http({
        "https://site.example/robots.txt": "User-agent: *\nDisallow: /private/\n",
        "https://site.example/": "<html>ok</html>",
    }, calls)

    async def scenario():
        client = PoliteClient(http, min_delay=0.5)
        assert await client.allowed("https://site.example/jobs/1")
        assert not await client.allowed("https://site.example/private/x")
        with pytest.raises(ingest_http.RobotsDisallowed):
            await client.get("https://site.example/private/x", check_robots=True)
        await client.get("https://site.example/jobs/1", check_robots=True)

    asyncio.run(scenario())
    assert all(r.headers["user-agent"] == USER_AGENT for r in calls)
    assert sum(1 for r in calls if r.url.path == "/robots.txt") == 1  # cached per host


@pytest.mark.parametrize("status,allowed", [(404, True), (500, False), (403, False)])
def test_robots_failure_modes(status, allowed):
    http = mock_http({"https://s.example/robots.txt": httpx.Response(status)})
    assert asyncio.run(PoliteClient(http).allowed("https://s.example/jobs")) is allowed


def test_requests_to_one_host_are_spaced_out(no_sleep):
    http = mock_http({"https://s.example/": "ok"})

    async def scenario():
        client = PoliteClient(http, min_delay=3.0)
        for _ in range(3):
            await client.get("https://s.example/page", check_robots=False)

    asyncio.run(scenario())
    assert len([s for s in no_sleep if s > 2.5]) == 2  # first request immediate, then spaced


def test_retry_after_is_honoured(no_sleep):
    responses = iter([httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, text="ok")])
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: next(responses)))
    resp = asyncio.run(PoliteClient(http, min_delay=0.5).get("https://s.example/x", check_robots=False))
    assert resp.status_code == 200 and 7 in no_sleep


# --- adapters through the full pipeline ----------------------------------

GREENHOUSE = {"jobs": [
    {"title": "Senior Data Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
     "location": {"name": "Remote, Worldwide"}, "content": "&lt;p&gt;Build pipelines in &lt;b&gt;Airflow&lt;/b&gt;&lt;/p&gt;"},
    {"title": "Account Executive", "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
     "location": {"name": "Remote"}, "content": ""},
    {"title": "Backend Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/3",
     "location": {"name": "San Francisco, CA"}, "content": ""},
    {"title": "Civil Site Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/4",
     "location": {"name": "Dhaka, Bangladesh"}, "content": "&lt;p&gt;AutoCAD, ETABS&lt;/p&gt;"},
]}
LEVER = [
    {"text": "Data Analyst", "hostedUrl": "https://jobs.lever.co/acme/a1", "workplaceType": "remote",
     "categories": {"location": "Anywhere", "commitment": "Full-time"}, "descriptionPlain": "SQL and Tableau",
     "lists": [{"text": "Requirements", "content": "<li>Power BI</li>"}],
     "salaryRange": {"min": 40000, "max": 60000, "currency": "USD", "interval": "per-year-salary"}},
]
ASHBY = {"jobs": [
    {"title": "Software Engineer", "jobUrl": "https://jobs.ashbyhq.com/acme/1", "isRemote": True,
     "location": "Remote", "employmentType": "Contract", "descriptionPlain": "React and TypeScript", "isListed": True},
    {"title": "Software Engineer (unlisted)", "jobUrl": "https://jobs.ashbyhq.com/acme/2", "isRemote": True,
     "location": "Remote", "isListed": False},
]}
SMARTRECRUITERS = {"totalFound": 1, "content": [
    {"id": "99", "name": "Electrical Engineer", "location": {"city": "Gazipur", "country": "bd", "remote": False},
     "typeOfEmployment": {"label": "Full-time"}, "company": {"name": "PowerCo"}},
]}


def test_ats_sources_end_to_end(client):
    cfg = config(
        {"name": "acme-gh", "type": "greenhouse", "board": "acme", "company": "Acme"},
        {"name": "acme-lv", "type": "lever", "board": "acme"},
        {"name": "acme-ab", "type": "ashby", "board": "acme"},
        {"name": "powerco", "type": "smartrecruiters", "board": "powerco"},
    )
    http = mock_http({
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs": GREENHOUSE,
        "https://api.lever.co/v0/postings/acme": LEVER,
        "https://api.ashbyhq.com/posting-api/job-board/acme": ASHBY,
        "https://api.smartrecruiters.com/v1/companies/powerco/postings": SMARTRECRUITERS,
    })
    summary = asyncio.run(run(cfg, http=http))
    by = {r["source"]: r for r in summary["sources"]}
    # Account Executive dropped at prefilter; San Francisco on-site dropped by location policy.
    assert by["acme-gh"]["kept"] == 2 and by["acme-gh"]["rejected"]["location"] == 1
    assert by["acme-lv"]["kept"] == 1 and by["acme-ab"]["kept"] == 1 and by["powerco"]["kept"] == 1
    assert summary["created"] == 5

    jobs = {j["title"]: j for j in client.get("/api/jobs", params={"page_size": 50}).json()["items"]}
    assert jobs["Senior Data Engineer"]["source"] == "gh:acme-gh"
    assert jobs["Senior Data Engineer"]["apply_url"] == "https://boards.greenhouse.io/acme/jobs/1"
    assert jobs["Senior Data Engineer"]["workplace"] == "remote"
    assert jobs["Civil Site Engineer"]["discipline"] == "civil" and jobs["Civil Site Engineer"]["workplace"] == "onsite"
    assert jobs["Data Analyst"]["salary_min"] == 40000 and jobs["Data Analyst"]["employment_type"] == "full_time"
    assert jobs["Software Engineer"]["employment_type"] == "contract"
    assert jobs["Electrical Engineer"]["apply_url"] == "https://jobs.smartrecruiters.com/powerco/99"
    detail = client.get(f"/api/jobs/{jobs['Senior Data Engineer']['id']}").json()
    assert "Airflow" in detail["description"] and "&lt;" not in detail["description"]


def test_keywords_narrow_results():
    cfg = config({"name": "acme-gh", "type": "greenhouse", "board": "acme"})
    http = mock_http({"https://boards-api.greenhouse.io": GREENHOUSE})
    summary = asyncio.run(run(cfg, http=http, dry_run=True, keywords=["civil"]))
    assert summary["sources"][0]["kept"] == 1
    assert summary["sources"][0]["sample"][0].startswith("Civil Site Engineer")


def test_complete_board_removes_filled_jobs_but_not_on_empty_response(client):
    cfg = config({"name": "acme-gh", "type": "greenhouse", "board": "acme"})
    asyncio.run(run(cfg, http=mock_http({"https://boards-api.greenhouse.io": GREENHOUSE})))
    assert client.get("/api/jobs").json()["total"] == 2

    smaller = {"jobs": [GREENHOUSE["jobs"][0]]}  # the civil job was filled
    report = asyncio.run(run(cfg, http=mock_http({"https://boards-api.greenhouse.io": smaller})))["sources"][0]
    assert report["removed"] == 1
    assert client.get("/api/jobs").json()["total"] == 1

    report = asyncio.run(run(cfg, http=mock_http({"https://boards-api.greenhouse.io": {"jobs": []}})))["sources"][0]
    assert report["removed"] == 0  # an empty board is treated as suspicious, not as "all filled"
    assert client.get("/api/jobs").json()["total"] == 1


def test_html_list_follows_detail_pages_and_respects_robots(client):
    listing = """
      <div class="job"><a class="t" href="/jobs/1">Data Analyst</a><span class="c">Acme BD</span><span class="l">Dhaka</span></div>
      <div class="job"><a class="t" href="/jobs/2">Sales Officer</a><span class="c">Acme BD</span><span class="l">Dhaka</span></div>
      <div class="job"><a class="t" href="/private/3">Civil Engineer</a>
        <span class="c">BuildCo</span><span class="l">Dhaka</span></div>
    """
    calls = []
    http = mock_http({
        "https://board.example/robots.txt": "User-agent: *\nDisallow: /private/\n",
        "https://board.example/list": listing,
        "https://board.example/jobs/1": jsonld_page(JOB_NODE),
    }, calls)
    cfg = config({
        "name": "bd-board", "type": "html_list", "terms_ok": True,
        "urls": ["https://board.example/list"],
        "selectors": {"item": ".job", "title": ".t", "link": "a.t", "company": ".c", "location": ".l"},
    })
    report = asyncio.run(run(cfg, http=http))["sources"][0]
    assert report["kept"] == 2  # Sales Officer filtered before any detail request
    paths = [r.url.path for r in calls]
    assert "/jobs/2" not in paths and "/private/3" not in paths  # filtered, and disallowed

    jobs = {j["title"]: j for j in client.get("/api/jobs").json()["items"]}
    rich = jobs["Data Analyst"]
    assert rich["apply_url"] == "https://board.example/jobs/1"
    assert rich["salary_min"] == 50000 and rich["deadline"] == "2099-01-31"
    assert jobs["Civil Engineer"]["apply_url"] == "https://board.example/private/3"  # listed, but its page never fetched


def test_scraping_requires_terms_ok_and_errors_are_isolated():
    cfg = config(
        {"name": "no-terms", "type": "jsonld_pages", "urls": ["https://x.example/jobs/1"]},
        {"name": "broken", "type": "greenhouse", "board": "broken"},
        {"name": "fine", "type": "greenhouse", "board": "acme"},
        {"name": "off", "type": "greenhouse", "board": "acme2", "enabled": False},
    )
    http = mock_http({
        "https://boards-api.greenhouse.io/v1/boards/broken": httpx.Response(500),
        "https://boards-api.greenhouse.io/v1/boards/acme/": GREENHOUSE,
    })
    by = {r["source"]: r for r in asyncio.run(run(cfg, http=http, dry_run=True))["sources"]}
    assert by["no-terms"]["status"] == "skipped" and "terms" in by["no-terms"]["reason"]
    assert by["broken"]["status"] == "error"
    assert by["fine"]["status"] == "ok" and by["fine"]["kept"] == 2
    assert by["off"]["status"] == "disabled"


def test_dry_run_writes_nothing(client):
    cfg = config({"name": "acme-gh", "type": "greenhouse", "board": "acme"})
    asyncio.run(run(cfg, http=mock_http({"https://boards-api.greenhouse.io": GREENHOUSE}), dry_run=True))
    assert client.get("/api/jobs").json()["total"] == 0


# --- rules & storage details ---------------------------------------------

def test_triage_rules():
    postings = [
        Posting(title="Data Analyst", company="A", url="https://a.example/1", location="Dhaka, Bangladesh"),
        Posting(title="Data Analyst", company="A", url="https://a.example/1", location="Dhaka"),  # duplicate link
        Posting(title="Data Analyst", company="A", url="https://a.example/2", location="Berlin"),
        Posting(title="Data Analyst", company="A", url="https://a.example/3", location="Berlin", remote=True),
        Posting(title="Data Analyst", company="A", url="javascript:alert(1)", location="Remote"),
        Posting(title="Nurse", company="A", url="https://a.example/4", location="Remote"),
    ]
    kept, reasons = triage(postings, [], "remote_or_bangladesh")
    assert [p.url for p in kept] == ["https://a.example/1", "https://a.example/3"]
    assert reasons == {"discipline": 1, "keyword": 0, "location": 1, "url": 1}
    assert len(triage(postings, [], "any")[0]) == 3


def test_scraped_descriptions_are_excerpts_and_hidden_jobs_stay_hidden(client, register):
    src = SourceConfig(name="bd-board", type="jsonld_pages", terms_ok=True, urls=["https://b.example/1"])
    posting = Posting(title="Data Analyst", company="A", url="https://b.example/1", location="Dhaka",
                      description="word " * 2000)
    save(src, [posting], datetime.now(UTC))
    job = client.get("/api/jobs").json()["items"][0]
    assert len(client.get(f"/api/jobs/{job['id']}").json()["description"]) <= 810

    admin = register("admin@example.com")
    client.post(f"/api/admin/jobs/{job['id']}/status", headers=admin, json={"status": "closed"})
    save(src, [posting], datetime.now(UTC) + timedelta(hours=6))
    assert client.get("/api/jobs").json()["total"] == 0


@pytest.mark.parametrize("bad", [
    {"name": "x", "type": "greenhouse", "board": "a"},  # name too short
    {"name": "Bad Name", "type": "greenhouse", "board": "a"},
    {"name": "needs-board", "type": "lever"},
    {"name": "needs-selectors", "type": "html_list", "urls": ["https://a.example"]},
    {"name": "needs-urls", "type": "jsonld_pages"},
])
def test_source_config_validation(bad):
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(bad)


def test_shipped_config_is_valid_and_templates_are_disabled():
    cfg = load_config()
    names = {s.name for s in cfg.sources}
    assert "public-apis" in names
    for src in cfg.sources:
        if src.is_scraping:
            assert not src.enabled and not src.terms_ok, f"{src.name} must not scrape without review"
    with pytest.raises(ValidationError):
        IngestConfig.model_validate({"sources": [{"name": "dup", "type": "public_apis"}] * 2})
