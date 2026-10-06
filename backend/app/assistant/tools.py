"""The assistant's tools: thin adapters over the same scorer, matcher and
catalog the rest of the app uses, so the agent's facts match what the UI shows.

Each tool returns (text for the model, events for the browser). Events let
the chat show real job cards and one-click edit suggestions instead of
re-describing them in prose. Tool inputs are model output: every one is
validated before it's used.
"""

from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, ValidationError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.analysis.pipeline import analyze_document
from app.core.executor import run_cpu_bound
from app.db.models import AssistantMemory, Job
from app.db.session import get_session_factory
from app.jobs.catalog import job_to_dict, list_open_jobs, normalize_skills, open_condition
from app.jobs.market import compute_market
from app.jobs.matcher import match_document
from app.schemas.jobs import Discipline, JobIn, Workplace
from app.schemas.resume import ResumeDocument

DISCIPLINES = ["data", "software", "civil", "electrical", "mechanical"]
WORKPLACES = ["onsite", "remote", "hybrid"]
EMPLOYMENT_TYPES = ["full_time", "part_time", "contract", "internship"]
MAX_DESCRIPTION_CHARS = 6000

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ToolError(Exception):
    """Reported back to the model as an is_error tool result."""


@dataclass
class ToolContext:
    user_id: str | None
    is_admin: bool
    document: ResumeDocument | None
    editable: bool
    job_description: str | None
    max_memories: int
    events: list[dict] = field(default_factory=list)

    def emit(self, name: str, data: dict) -> None:
        self.events.append({"event": name, "data": data})


# ---------- Definitions ----------

def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        # Inputs stream as they're generated; run_tool validates them.
        "eager_input_streaming": True,
        "input_schema": {"type": "object", "properties": properties, "required": required},
    }


SCORE_RESUME = _tool(
    "score_resume",
    "Run Prottoy's ATS scan on the open resume. Returns the overall and component scores, the top suggestions, "
    "weak bullets, and (with a job description) the missing keywords. Uses the target job description from the "
    "context unless you pass one.",
    {"job_description": {"type": "string", "description": "Optional job description to score against."}},
    [],
)
SUGGEST_EDITS = _tool(
    "suggest_edits",
    "Propose changes to the open resume. The user sees each change with Apply and Dismiss buttons; nothing changes "
    "until they apply it. Indexes refer to the [i] / [i.j] labels in the resume context.",
    {
        "note": {"type": "string", "description": "One short sentence shown above the suggestions: why these changes help."},
        "edits": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": [
                        "summary", "headline", "replace_bullet", "add_bullet", "add_skills", "replace_project_bullet",
                    ]},
                    "experience_index": {"type": "integer", "description": "For replace_bullet / add_bullet."},
                    "project_index": {"type": "integer", "description": "For replace_project_bullet."},
                    "bullet_index": {"type": "integer", "description": "For replace_bullet / replace_project_bullet."},
                    "text": {"type": "string", "description": "The new text (all kinds except add_skills)."},
                    "skills": {"type": "array", "items": {"type": "string"}, "description": "For add_skills."},
                },
                "required": ["kind"],
            },
        },
    },
    ["note", "edits"],
)
FIND_JOBS = _tool(
    "find_jobs",
    "Search Prottoy's open jobs. With a resume open, results are ranked by match score with matched and missing "
    "skills; without one, they're the newest matches for the query. The user sees the results as cards with "
    "Apply links.",
    {
        "query": {"type": "string", "description": "Keywords for title, company or skills, e.g. 'data analyst'."},
        "discipline": {"type": "string", "enum": DISCIPLINES},
        "workplace": {"type": "string", "enum": WORKPLACES},
        "limit": {"type": "integer", "minimum": 1, "maximum": 8, "description": "Default 5."},
    },
    [],
)
GET_JOB = _tool(
    "get_job",
    "Get one open job's full posting: description, skills, experience and salary, location, apply link.",
    {"job_id": {"type": "string"}},
    ["job_id"],
)
MARKET_SIGNAL = _tool(
    "market_signal",
    "Job-market signals from Prottoy's open listings: most-demanded skills (with recent vs previous two weeks), "
    "top hiring companies and locations, work-mode split, and median monthly salary where postings list one.",
    {
        "discipline": {"type": "string", "enum": DISCIPLINES},
        "workplace": {"type": "string", "enum": WORKPLACES},
    },
    [],
)
REMEMBER = _tool(
    "remember",
    "Save a durable fact about the user for future conversations, e.g. 'Targets junior data analyst roles in Dhaka' "
    "or 'Prefers remote work'. One fact per call, under 200 characters.",
    {"fact": {"type": "string"}},
    ["fact"],
)
SAVE_JOB_DRAFT = _tool(
    "save_job_draft",
    "Admins only: save a job description as a draft listing on Prottoy. Drafts aren't public until an admin "
    "publishes them from the admin page.",
    {
        "title": {"type": "string"},
        "company": {"type": "string"},
        "location": {"type": "string"},
        "discipline": {"type": "string", "enum": DISCIPLINES},
        "workplace": {"type": "string", "enum": WORKPLACES},
        "employment_type": {"type": "string", "enum": EMPLOYMENT_TYPES},
        "experience_min": {"type": "number"},
        "experience_max": {"type": "number"},
        "salary_min": {"type": "integer", "description": "BDT per month unless salary_currency says otherwise."},
        "salary_max": {"type": "integer"},
        "salary_currency": {"type": "string", "description": "ISO code, default BDT."},
        "description": {"type": "string", "description": "The full job description, plain text with '- ' bullets."},
        "skills": {"type": "array", "items": {"type": "string"}},
        "apply_url": {"type": "string", "description": "http(s) URL or mailto: address, if known."},
    },
    ["title", "company", "discipline", "description"],
)


def tools_for(ctx: ToolContext) -> list[dict]:
    """Only the tools that can work on this page. Order is fixed."""
    tools = []
    if ctx.document is not None:
        tools.append(SCORE_RESUME)
    if ctx.document is not None and ctx.editable:
        tools.append(SUGGEST_EDITS)
    tools += [FIND_JOBS, GET_JOB, MARKET_SIGNAL, REMEMBER]
    if ctx.is_admin:
        tools.append(SAVE_JOB_DRAFT)
    return tools


# ---------- Input models ----------

class ScoreIn(BaseModel):
    job_description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20_000)] | None = None


class EditIn(BaseModel):
    kind: Literal["summary", "headline", "replace_bullet", "add_bullet", "add_skills", "replace_project_bullet"]
    experience_index: int | None = None
    project_index: int | None = None
    bullet_index: int | None = None
    text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    skills: Annotated[list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]],
                      Field(max_length=30)] | None = None


class SuggestIn(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ""
    edits: Annotated[list[EditIn], Field(min_length=1, max_length=12)]


class FindJobsIn(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    discipline: Discipline | None = None
    workplace: Workplace | None = None
    limit: Annotated[int, Field(ge=1, le=8)] = 5


class GetJobIn(BaseModel):
    job_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class MarketIn(BaseModel):
    discipline: Discipline | None = None
    workplace: Workplace | None = None


class RememberIn(BaseModel):
    fact: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


# ---------- Implementations ----------

async def score_resume(ctx: ToolContext, args: ScoreIn) -> str:
    jd = args.job_description or ctx.job_description
    result = await run_cpu_bound(analyze_document, ctx.document, jd)
    lines = [
        f"ATS score: {result['ats_score']}/100 (formatting {result['formatting_score']}, "
        f"content {result['content_score']}, keywords {result['keyword_score']})",
        "Scored against: " + ("the job description" if jd else "general best practice (no job description)"),
    ]
    if result["suggestions"]:
        lines.append("Top suggestions:\n" + "\n".join(f"- {s}" for s in result["suggestions"][:8]))
    if result["keywords"]["missing"]:
        lines.append("Missing job keywords: " + ", ".join(result["keywords"]["missing"][:15]))
    if result["flagged_lines"]:
        lines.append("Weak bullets:\n" + "\n".join(
            f"- \"{f['text']}\" ({'; '.join(f['reasons'])})" for f in result["flagged_lines"][:6]))
    ctx.emit("score", {"ats_score": result["ats_score"]})
    return "\n".join(lines)


def _label_role(doc: ResumeDocument, i: int) -> str:
    role = doc.experience[i]
    return " at ".join(p for p in (role.title, role.company) if p) or f"Role {i + 1}"


def _resolve(doc: ResumeDocument, edit: EditIn) -> dict:
    """Checks one edit against the resume and returns it with what it replaces."""
    def need_text():
        if not edit.text:
            raise ToolError(f"{edit.kind} needs 'text'.")
        return edit.text

    def role_index(items, index, what):
        if index is None or not 0 <= index < len(items):
            raise ToolError(f"{what} index {index} doesn't exist (there are {len(items)}).")
        return index

    out = {"kind": edit.kind}
    if edit.kind in ("summary", "headline"):
        out |= {"label": edit.kind.capitalize(), "before": getattr(doc.basics, edit.kind), "after": need_text()}
    elif edit.kind in ("replace_bullet", "add_bullet"):
        i = role_index(doc.experience, edit.experience_index, "Experience")
        bullets = doc.experience[i].bullets
        out["experience_index"] = i
        if edit.kind == "replace_bullet":
            j = role_index(bullets, edit.bullet_index, f"Bullet in experience {i}")
            out |= {"bullet_index": j, "label": f"{_label_role(doc, i)} · bullet {j + 1}", "before": bullets[j]}
        else:
            if len(bullets) >= 15:
                raise ToolError(f"Experience {i} already has the maximum 15 bullets.")
            out |= {"label": f"{_label_role(doc, i)} · new bullet", "before": ""}
        out["after"] = need_text()
    elif edit.kind == "replace_project_bullet":
        i = role_index(doc.projects, edit.project_index, "Project")
        bullets = doc.projects[i].bullets
        j = role_index(bullets, edit.bullet_index, f"Bullet in project {i}")
        out |= {"project_index": i, "bullet_index": j, "before": bullets[j], "after": need_text(),
                "label": f"{doc.projects[i].name or f'Project {i + 1}'} · bullet {j + 1}"}
    else:  # add_skills
        have = {s.lower() for s in doc.all_skills()}
        new = list(dict.fromkeys(s for s in (edit.skills or []) if s.lower() not in have))
        if not new:
            raise ToolError("Those skills are already on the resume (or none were given).")
        out |= {"label": "Skills", "before": "", "after": ", ".join(new), "skills": new}
    return out


async def suggest_edits(ctx: ToolContext, args: SuggestIn) -> str:
    edits, problems = [], []
    for n, edit in enumerate(args.edits):
        try:
            edits.append(_resolve(ctx.document, edit))
        except ToolError as exc:
            problems.append(f"Edit {n + 1}: {exc}")
    if not edits:
        raise ToolError("No valid edits. " + " ".join(problems))
    ctx.emit("proposal", {"note": args.note, "edits": edits})
    shown = f"Showed the user {len(edits)} suggested edit(s) with Apply buttons; they aren't applied yet."
    return shown + (" Skipped: " + " ".join(problems) if problems else "")


def _job_card(job: dict, match: dict | None = None) -> dict:
    card = {k: job[k] for k in ("id", "title", "company", "location", "workplace", "apply_url")}
    if match:
        card |= {"match_score": match["match_score"], "matched_skills": match["matched_skills"][:6],
                 "missing_skills": match["missing_skills"][:6]}
    return card


async def find_jobs(ctx: ToolContext, args: FindJobsIn) -> str:
    if ctx.document is not None:
        result = await run_cpu_bound(match_document, ctx.document, discipline=args.discipline,
                                     workplace=args.workplace, q=args.query, limit=args.limit)
        cards = [_job_card(r["job"], r) for r in result["results"]]
    else:
        def query():
            with get_session_factory()() as db:
                return list_open_jobs(db, discipline=args.discipline, q=args.query, workplace=args.workplace,
                                      page=1, page_size=args.limit)
        cards = [_job_card(j) for j in (await run_in_threadpool(query))["items"]]

    if not cards:
        return "No open jobs match that search. Suggest broadening it (fewer keywords, no discipline filter)."
    ctx.emit("jobs", {"jobs": cards})
    lines = []
    for c in cards:
        line = f"- id={c['id']} | {c['title']} at {c['company']} | {c['location'] or c['workplace']}"
        if "match_score" in c:
            line += (f" | match {round(c['match_score'])}% | has: {', '.join(c['matched_skills']) or 'none'}"
                     f" | missing: {', '.join(c['missing_skills']) or 'none'}")
        lines.append(line)
    return "The user can see these as cards with Apply links:\n" + "\n".join(lines)


async def get_job(ctx: ToolContext, args: GetJobIn) -> str:
    def load():
        with get_session_factory()() as db:
            job = db.scalar(select(Job).where(Job.id == args.job_id, open_condition()))
            return job_to_dict(job, with_description=True) if job else None
    job = await run_in_threadpool(load)
    if job is None:
        raise ToolError("No open job with that id.")
    description = job["description"][:MAX_DESCRIPTION_CHARS]
    facts = [
        f"{job['title']} at {job['company']} — {job['location'] or job['workplace']} ({job['workplace']}, "
        f"{job['employment_type']})",
        f"Skills: {', '.join(job['skills']) or 'not listed'}",
        f"Experience: {job['experience_min']}–{job['experience_max']} years" if job["experience_min"] is not None
        else "Experience: not stated",
        f"Apply: {job['apply_url'] or 'see posting'}",
        f"Deadline: {job['deadline'] or 'none'}",
    ]
    return "\n".join(facts) + f"\n<job_posting>\n{description}\n</job_posting>"


async def market_signal(ctx: ToolContext, args: MarketIn) -> str:
    def load():
        with get_session_factory()() as db:
            return compute_market(db, discipline=args.discipline, workplace=args.workplace)
    m = await run_in_threadpool(load)
    t = m["totals"]
    if not t["open_jobs"]:
        return "No open jobs match those filters right now."
    salary = m["salary"]
    lines = [
        f"{t['open_jobs']} open jobs from {t['companies']} companies; {t['new_7d']} new this week; "
        f"{t['remote_jobs']} remote, {t['local_jobs']} in Bangladesh.",
        "Top skills (open jobs | last 14 days vs the 14 before): " + "; ".join(
            f"{s['name']} {s['count']} ({s['recent']} vs {s['previous']})" for s in m["skills"]),
        "Top hiring companies: " + ", ".join(f"{c['name']} ({c['count']})" for c in m["companies"]),
        "Locations: " + ", ".join(f"{c['name']} ({c['count']})" for c in m["locations"]),
        "Work mode: " + ", ".join(f"{w['key']} {w['count']}" for w in m["workplaces"]),
        (f"Median salary: BDT {salary['median']:,}/month from {salary['samples']} postings that list one"
         if salary["median"] else f"Salary: only {salary['samples']} postings list one; too few for a median."),
    ]
    return "\n".join(lines)


async def remember(ctx: ToolContext, args: RememberIn) -> str:
    if ctx.user_id is None:
        ctx.emit("memory", {"fact": args.fact, "stored": "browser"})
        return "Saved in this browser (the user isn't signed in)."

    def save():
        with get_session_factory()() as db:
            db.add(AssistantMemory(user_id=ctx.user_id, text=args.fact))
            db.flush()
            ids = db.scalars(select(AssistantMemory.id).where(AssistantMemory.user_id == ctx.user_id)
                             .order_by(AssistantMemory.created_at.desc(), AssistantMemory.id)).all()
            for stale in ids[ctx.max_memories:]:
                db.delete(db.get(AssistantMemory, stale))
            db.commit()
    await run_in_threadpool(save)
    ctx.emit("memory", {"fact": args.fact, "stored": "account"})
    return "Saved to the user's account."


async def save_job_draft(ctx: ToolContext, args: dict) -> str:
    try:
        body = JobIn(**{**args, "status": "draft"})
    except ValidationError as exc:
        raise ToolError("Invalid job: " + "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:5])) from exc

    def save():
        with get_session_factory()() as db:
            data = body.model_dump()
            data["skills"] = normalize_skills(body.skills, body.title, body.description)
            job = Job(**data, source="local", created_by=ctx.user_id)
            db.add(job)
            db.commit()
            return job.id
    job_id = await run_in_threadpool(save)
    ctx.emit("job_draft", {"id": job_id, "title": body.title, "company": body.company})
    return f"Saved as draft job {job_id}. An admin can review and publish it on the admin page."


HANDLERS = {
    "score_resume": (ScoreIn, score_resume),
    "suggest_edits": (SuggestIn, suggest_edits),
    "find_jobs": (FindJobsIn, find_jobs),
    "get_job": (GetJobIn, get_job),
    "market_signal": (MarketIn, market_signal),
    "remember": (RememberIn, remember),
    "save_job_draft": (None, save_job_draft),
}


async def run_tool(ctx: ToolContext, name: str, raw_input) -> tuple[str, bool]:
    """Returns (content, is_error). Never raises for bad model input."""
    allowed = {t["name"] for t in tools_for(ctx)}
    if name not in allowed:
        return f"Tool {name} isn't available here.", True
    model, handler = HANDLERS[name]
    if not isinstance(raw_input, dict):
        return '{"INVALID_JSON": "tool input was not an object"}', True
    try:
        args = model(**raw_input) if model else raw_input
        return await handler(ctx, args), False
    except ValidationError as exc:
        return "Invalid input: " + "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:5]), True
    except ToolError as exc:
        return str(exc), True
