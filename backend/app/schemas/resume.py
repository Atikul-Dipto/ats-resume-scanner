"""The builder's core data model: a resume as structured data, not a file.

Everything downstream — live scoring, PDF/DOCX export, the stored JSON in
resumes.document — is derived from this one shape. Length limits double as
abuse protection, since documents are accepted from anonymous callers too.
"""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

SCHEMA_VERSION = 1

# "", "2021", or "2021-03" (what an <input type="month"> produces).
DATE_RE = re.compile(r"^(\d{4}(-(0[1-9]|1[0-2]))?)?$")

ShortStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
LineStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
DateStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=7)]
Bullets = Annotated[list[LineStr], Field(default_factory=list, max_length=15)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Dated(_Strict):
    start: DateStr = ""
    end: DateStr = ""

    @field_validator("start", "end")
    @classmethod
    def _check_date(cls, value: str) -> str:
        if not DATE_RE.match(value):
            raise ValueError("Dates must be YYYY or YYYY-MM.")
        return value


class Link(_Strict):
    label: ShortStr = ""
    url: ShortStr


class Basics(_Strict):
    name: ShortStr = ""
    headline: ShortStr = ""
    email: ShortStr = ""
    phone: ShortStr = ""
    location: ShortStr = ""
    links: Annotated[list[Link], Field(default_factory=list, max_length=6)]
    summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""


class ExperienceItem(_Dated):
    title: ShortStr = ""
    company: ShortStr = ""
    location: ShortStr = ""
    current: bool = False
    bullets: Bullets


class EducationItem(_Dated):
    institution: ShortStr = ""
    degree: ShortStr = ""
    location: ShortStr = ""
    details: Bullets


class SkillGroup(_Strict):
    name: ShortStr = ""
    skills: Annotated[list[ShortStr], Field(default_factory=list, max_length=60)]


class ProjectItem(_Strict):
    name: ShortStr = ""
    url: ShortStr = ""
    bullets: Bullets


class CertificationItem(_Strict):
    name: ShortStr = ""
    issuer: ShortStr = ""
    date: DateStr = ""

    @field_validator("date")
    @classmethod
    def _check_date(cls, value: str) -> str:
        if not DATE_RE.match(value):
            raise ValueError("Dates must be YYYY or YYYY-MM.")
        return value


class ResumeDocument(_Strict):
    schema_version: int = SCHEMA_VERSION
    template: Literal["classic", "compact"] = "classic"
    basics: Basics = Field(default_factory=Basics)
    experience: Annotated[list[ExperienceItem], Field(default_factory=list, max_length=20)]
    education: Annotated[list[EducationItem], Field(default_factory=list, max_length=10)]
    skills: Annotated[list[SkillGroup], Field(default_factory=list, max_length=10)]
    projects: Annotated[list[ProjectItem], Field(default_factory=list, max_length=15)]
    certifications: Annotated[list[CertificationItem], Field(default_factory=list, max_length=20)]

    def all_skills(self) -> list[str]:
        seen: dict[str, None] = {}
        for group in self.skills:
            for skill in group.skills:
                if skill:
                    seen.setdefault(skill, None)
        return list(seen)
