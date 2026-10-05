"""Shapes shared by every ingestion adapter."""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

SourceType = Literal["public_apis", "greenhouse", "lever", "ashby", "smartrecruiters", "jsonld_pages", "html_list"]
LocationPolicy = Literal["remote_or_bangladesh", "remote", "bangladesh", "any"]

# Types that read pages a site serves to browsers (rather than an API the
# site offers for programmatic use) — these must honour robots.txt and need
# the operator to confirm the site's terms allow it.
SCRAPING_TYPES = {"jsonld_pages", "html_list"}

# Short prefixes keep "<prefix>:<name>" inside the 30-char jobs.source column.
SOURCE_PREFIX = {
    "greenhouse": "gh", "lever": "lv", "ashby": "ab", "smartrecruiters": "sr",
    "jsonld_pages": "ld", "html_list": "web",
}


@dataclass
class Posting:
    """One job as an adapter found it, before filtering."""

    title: str
    company: str
    url: str  # where the candidate applies / reads the full posting
    location: str = ""
    description: str = ""  # plain text
    remote: bool | None = None
    employment_type: str | None = None  # full_time | part_time | contract | internship
    deadline: date | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None  # month | year
    extra: dict = field(default_factory=dict)


class Selectors(BaseModel):
    """CSS selectors for an html_list source. `item` matches one job row;
    the rest are evaluated inside it. `link` must select an <a>."""

    item: str
    title: str
    link: str
    company: str | None = None
    location: str | None = None


class SourceConfig(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,23}$")
    type: SourceType
    enabled: bool = True
    company: str | None = None  # display name for single-company boards
    board: str | None = None  # greenhouse/lever/ashby/smartrecruiters board id
    keywords: list[str] = []
    location_policy: LocationPolicy | None = None
    # Scraping-only settings
    terms_ok: bool = False  # operator has read the site's terms and they allow this
    urls: list[HttpUrl] = []  # pages to read (jsonld_pages) or list pages (html_list)
    sitemap: HttpUrl | None = None  # jsonld_pages: discover detail pages from a sitemap
    url_pattern: str | None = None  # regex a sitemap URL must match
    max_pages: int = Field(default=50, ge=1, le=500)
    selectors: Selectors | None = None
    follow_detail: bool = True  # html_list: read JSON-LD on each job's own page
    notes: str = ""

    @model_validator(mode="after")
    def _check(self):
        if self.type in {"greenhouse", "lever", "ashby", "smartrecruiters"} and not self.board:
            raise ValueError(f"{self.name}: '{self.type}' sources need a 'board'.")
        if self.type == "html_list" and (not self.selectors or not self.urls):
            raise ValueError(f"{self.name}: html_list sources need 'urls' and 'selectors'.")
        if self.type == "jsonld_pages" and not (self.urls or self.sitemap):
            raise ValueError(f"{self.name}: jsonld_pages sources need 'urls' or a 'sitemap'.")
        return self

    @property
    def is_scraping(self) -> bool:
        return self.type in SCRAPING_TYPES

    @property
    def source_key(self) -> str:
        return f"{SOURCE_PREFIX.get(self.type, self.type)}:{self.name}"[:30]

    @property
    def complete(self) -> bool:
        """True when one fetch returns the source's *entire* current list, so a
        job missing from a successful fetch has been filled or withdrawn."""
        return self.type in {"greenhouse", "lever", "ashby", "smartrecruiters"}


class IngestConfig(BaseModel):
    keywords: list[str] = []
    location_policy: LocationPolicy = "remote_or_bangladesh"
    min_delay_seconds: float = Field(default=2.0, ge=0.5, le=60)
    sources: list[SourceConfig]

    @model_validator(mode="after")
    def _unique(self):
        names = [s.name for s in self.sources]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"Duplicate source names: {sorted(dupes)}")
        return self
