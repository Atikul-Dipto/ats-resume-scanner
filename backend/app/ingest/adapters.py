"""One fetcher per source type. Each returns Postings; filtering and storage
live in pipeline.py so every source is held to the same rules.

Official APIs (no robots check — they exist for programmatic access):
  greenhouse       https://developers.greenhouse.io/job-board.html
  lever            https://github.com/lever/postings-api
  ashby            https://developers.ashbyhq.com/docs/public-job-posting-api
  smartrecruiters  https://developers.smartrecruiters.com/docs/posting-api
  workable         the public jobs widget API (apply.workable.com/api/v1/widget/accounts/<account>)
  recruitee        the public careers-site API (<company>.recruitee.com/api/offers/)
Scraping (robots.txt checked for every URL, and only with terms_ok: true):
  jsonld_pages     schema.org JobPosting embedded in career pages
  html_list        a listing page read with CSS selectors
"""

import html
import re
from collections.abc import Awaitable, Callable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.ingest.http import PoliteClient, RobotsDisallowed
from app.ingest.jsonld import postings_from_html
from app.ingest.models import Posting, SourceConfig
from app.jobs.catalog_sync import html_to_text

PrefilterFn = Callable[[str], bool]

_EMPLOYMENT_WORDS = {
    "fulltime": "full_time", "full-time": "full_time", "full time": "full_time", "permanent": "full_time",
    "parttime": "part_time", "part-time": "part_time", "part time": "part_time",
    "contract": "contract", "contractor": "contract", "temporary": "contract", "freelance": "contract",
    "intern": "internship", "internship": "internship",
}


def employment_from(text: str | None) -> str | None:
    lowered = (text or "").lower()
    for word, value in _EMPLOYMENT_WORDS.items():
        if word in lowered:
            return value
    return None


async def fetch_greenhouse(client: PoliteClient, src: SourceConfig, prefilter: PrefilterFn) -> list[Posting]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{src.board}/jobs?content=true"
    data = (await client.get(url, check_robots=False)).json()
    postings = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        if not prefilter(title):
            continue
        location = (job.get("location") or {}).get("name", "")
        postings.append(Posting(
            title=title,
            company=src.company or src.board,
            url=job.get("absolute_url", ""),
            location=location,
            # Greenhouse returns HTML entity-escaped HTML.
            description=html_to_text(html.unescape(job.get("content") or "")),
            remote=True if "remote" in location.lower() else None,
        ))
    return postings


async def fetch_lever(client: PoliteClient, src: SourceConfig, prefilter: PrefilterFn) -> list[Posting]:
    data = (await client.get(f"https://api.lever.co/v0/postings/{src.board}?mode=json", check_robots=False)).json()
    postings = []
    for job in data if isinstance(data, list) else []:
        title = job.get("text", "")
        if not prefilter(title):
            continue
        categories = job.get("categories") or {}
        sections = "\n\n".join(
            f"{s.get('text', '')}\n{html_to_text(s.get('content', ''))}" for s in job.get("lists") or []
        )
        salary = job.get("salaryRange") or {}
        postings.append(Posting(
            title=title,
            company=src.company or src.board,
            url=job.get("hostedUrl") or job.get("applyUrl", ""),
            location=categories.get("location", "") or "",
            description="\n\n".join(p for p in (job.get("descriptionPlain"), sections, job.get("additionalPlain")) if p),
            remote=True if (job.get("workplaceType") == "remote") else None,
            employment_type=employment_from(categories.get("commitment")),
            salary_min=salary.get("min"),
            salary_max=salary.get("max"),
            salary_currency=(salary.get("currency") or None),
            salary_period="year" if "year" in str(salary.get("interval", "")).lower() else None,
        ))
    return postings


async def fetch_ashby(client: PoliteClient, src: SourceConfig, prefilter: PrefilterFn) -> list[Posting]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{src.board}?includeCompensation=false"
    data = (await client.get(url, check_robots=False)).json()
    postings = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        if job.get("isListed") is False or not prefilter(title):
            continue
        postings.append(Posting(
            title=title,
            company=src.company or src.board,
            url=job.get("jobUrl") or job.get("applyUrl", ""),
            location=job.get("location", "") or "",
            description=job.get("descriptionPlain") or html_to_text(job.get("descriptionHtml") or ""),
            remote=True if job.get("isRemote") or job.get("workplaceType") == "Remote" else None,
            employment_type=employment_from(job.get("employmentType")),
        ))
    return postings


async def fetch_smartrecruiters(client: PoliteClient, src: SourceConfig, prefilter: PrefilterFn) -> list[Posting]:
    postings, offset = [], 0
    while offset < 1000:
        url = f"https://api.smartrecruiters.com/v1/companies/{src.board}/postings?limit=100&offset={offset}"
        data = (await client.get(url, check_robots=False)).json()
        page = data.get("content", [])
        for job in page:
            title = job.get("name", "")
            if not prefilter(title):
                continue
            loc = job.get("location") or {}
            postings.append(Posting(
                title=title,
                company=src.company or (job.get("company") or {}).get("name") or src.board,
                url=f"https://jobs.smartrecruiters.com/{src.board}/{job.get('id')}",
                location=", ".join(p for p in (loc.get("city"), loc.get("country")) if p),
                remote=True if loc.get("remote") else None,
                employment_type=employment_from((job.get("typeOfEmployment") or {}).get("label")),
            ))
        offset += 100
        if offset >= int(data.get("totalFound", 0)) or not page:
            break
    return postings


_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)


async def _sitemap_urls(client: PoliteClient, src: SourceConfig) -> list[str]:
    xml = (await client.get(str(src.sitemap), check_robots=True)).text
    pattern = re.compile(src.url_pattern) if src.url_pattern else None
    urls = [u for u in _LOC_RE.findall(xml) if not pattern or pattern.search(u)]
    return urls[: src.max_pages]


async def fetch_jsonld_pages(client: PoliteClient, src: SourceConfig, prefilter: PrefilterFn) -> list[Posting]:
    urls = [str(u) for u in src.urls] + (await _sitemap_urls(client, src) if src.sitemap else [])
    postings = []
    for url in list(dict.fromkeys(urls))[: src.max_pages]:
        try:
            page = await client.get(url, check_robots=True)
        except RobotsDisallowed:
            continue
        for posting in postings_from_html(page.text, url):
            if prefilter(posting.title):
                posting.company = posting.company or src.company or ""
                postings.append(posting)
    return postings


def _text(node, selector: str | None) -> str:
    if not selector:
        return ""
    found = node.select_one(selector)
    return " ".join(found.get_text(" ").split()) if found else ""


async def fetch_html_list(client: PoliteClient, src: SourceConfig, prefilter: PrefilterFn) -> list[Posting]:
    sel = src.selectors
    postings, detail_reads = [], 0
    for list_url in [str(u) for u in src.urls]:
        page = await client.get(list_url, check_robots=True)
        soup = BeautifulSoup(page.text, "lxml")
        for item in soup.select(sel.item):
            title = _text(item, sel.title)
            link = item.select_one(sel.link)
            href = link.get("href") if link else None
            if not title or not href or not prefilter(title):
                continue
            url = urljoin(list_url, href)
            posting = Posting(
                title=title, url=url,
                company=_text(item, sel.company) or src.company or "",
                location=_text(item, sel.location),
            )
            if src.follow_detail and detail_reads < src.max_pages:
                detail_reads += 1
                try:
                    detail = await client.get(url, check_robots=True)
                    structured = postings_from_html(detail.text, url)
                except RobotsDisallowed:
                    structured = []
                if structured:
                    rich = structured[0]
                    rich.url = url  # apply where the listing pointed
                    rich.company = rich.company or posting.company
                    rich.location = rich.location or posting.location
                    posting = rich
            postings.append(posting)
    return postings


def _place(*parts) -> str:
    return ", ".join(dict.fromkeys(p.strip() for p in parts if p and p.strip()))


async def fetch_workable(client: PoliteClient, src: SourceConfig, prefilter: PrefilterFn) -> list[Posting]:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{src.board}?details=true"
    data = (await client.get(url, check_robots=False)).json()
    postings = []
    for job in data.get("jobs", []) if isinstance(data, dict) else []:
        title = job.get("title", "")
        if not prefilter(title):
            continue
        places = job.get("locations") or [{}]
        location = _place(places[0].get("city") or job.get("city"), places[0].get("country") or job.get("country"))
        postings.append(Posting(
            title=title,
            company=src.company or data.get("name") or src.board,
            url=job.get("url") or job.get("application_url") or job.get("shortlink", ""),
            location=location,
            description=html_to_text(job.get("description") or ""),
            remote=True if job.get("telecommuting") else None,
            employment_type=employment_from(job.get("employment_type")),
        ))
    return postings


async def fetch_recruitee(client: PoliteClient, src: SourceConfig, prefilter: PrefilterFn) -> list[Posting]:
    data = (await client.get(f"https://{src.board}.recruitee.com/api/offers/", check_robots=False)).json()
    postings = []
    for job in data.get("offers", []) if isinstance(data, dict) else []:
        title = job.get("title", "")
        if job.get("status", "published") != "published" or not prefilter(title):
            continue
        description = "\n\n".join(html_to_text(job.get(k) or "") for k in ("description", "requirements") if job.get(k))
        postings.append(Posting(
            title=title,
            company=src.company or job.get("company_name") or src.board,
            url=job.get("careers_url") or job.get("careers_apply_url", ""),
            location=job.get("location") or _place(job.get("city"), job.get("country")),
            description=description,
            remote=True if job.get("remote") else None,
            employment_type=employment_from(job.get("employment_type_code")),
        ))
    return postings


FETCHERS: dict[str, Callable[[PoliteClient, SourceConfig, PrefilterFn], Awaitable[list[Posting]]]] = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "workable": fetch_workable,
    "recruitee": fetch_recruitee,
    "jsonld_pages": fetch_jsonld_pages,
    "html_list": fetch_html_list,
}
