"""Reads schema.org JobPosting data embedded in pages.

Career sites embed this for Google for Jobs, which makes it the most stable
thing to read: it's published precisely so machines can consume it, and it
doesn't break when the page's visual layout changes.
"""

import json
import re
from datetime import date

from app.ingest.models import Posting
from app.jobs.catalog_sync import html_to_text

_SCRIPT_RE = re.compile(
    r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL
)
_EMPLOYMENT = {
    "FULL_TIME": "full_time", "PART_TIME": "part_time", "CONTRACTOR": "contract",
    "TEMPORARY": "contract", "INTERN": "internship", "INTERNSHIP": "internship",
}
_PERIOD = {"MONTH": "month", "YEAR": "year"}


def _walk(node):
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        yield node
        if "@graph" in node:
            yield from _walk(node["@graph"])


def _is_job_posting(node: dict) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return "JobPosting" in kinds


def _text(value) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("@value") or "")
    if isinstance(value, list):
        return ", ".join(t for t in (_text(v) for v in value) if t)
    return str(value or "")


def _location(node: dict) -> str:
    places = node.get("jobLocation") or []
    places = places if isinstance(places, list) else [places]
    parts = []
    for place in places:
        address = place.get("address", {}) if isinstance(place, dict) else {}
        if isinstance(address, str):
            parts.append(address)
            continue
        bits = [_text(address.get(k)) for k in ("addressLocality", "addressRegion", "addressCountry")]
        label = ", ".join(dict.fromkeys(b for b in bits if b))
        if label:
            parts.append(label)
    return "; ".join(dict.fromkeys(parts))[:200]


def _date(value) -> date | None:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value or ""))
    if not match:
        return None
    try:
        return date(*map(int, match.groups()))
    except ValueError:
        return None


def _salary(node: dict) -> dict:
    base = node.get("baseSalary")
    if not isinstance(base, dict):
        return {}
    value = base.get("value", {})
    value = value if isinstance(value, dict) else {"value": value}

    def num(v):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    low = num(value.get("minValue", value.get("value")))
    high = num(value.get("maxValue", value.get("value")))
    period = _PERIOD.get(str(value.get("unitText", "")).upper())
    currency = str(base.get("currency") or "")[:3].upper() or None
    if low is None and high is None:
        return {}
    return {"salary_min": low, "salary_max": high, "salary_currency": currency, "salary_period": period}


def postings_from_html(html: str, page_url: str) -> list[Posting]:
    found = []
    for raw in _SCRIPT_RE.findall(html):
        raw = raw.strip().removeprefix("<!--").removesuffix("-->").strip()
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        for node in _walk(data):
            if not _is_job_posting(node):
                continue
            title = _text(node.get("title")).strip()
            if not title:
                continue
            employment = node.get("employmentType")
            employment = employment[0] if isinstance(employment, list) and employment else employment
            location_type = str(node.get("jobLocationType", "")).upper()
            found.append(Posting(
                title=title,
                company=_text(node.get("hiringOrganization")).strip() or "",
                # The page itself is where people read and apply.
                url=str(node.get("url") or page_url),
                location=_location(node),
                description=html_to_text(str(node.get("description") or "")),
                remote=True if location_type == "TELECOMMUTE" else None,
                employment_type=_EMPLOYMENT.get(str(employment or "").upper()),
                deadline=_date(node.get("validThrough")),
                **_salary(node),
            ))
    return found
