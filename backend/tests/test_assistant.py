"""The assistant, driven by a scripted fake of the Anthropic client: each
model "round" is a canned message, so these tests exercise the real loop,
tools, context and SSE stream without network access."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.assistant import client as assistant_client
from app.assistant.prompt import render_resume
from app.core.config import get_settings
from app.db.models import AssistantMemory, Job
from app.db.session import get_session_factory
from app.schemas.resume import ResumeDocument
from tests.test_job_board import ADMIN, job_payload

USAGE = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0)


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool(name, args, id_=None):
    return SimpleNamespace(type="tool_use", id=id_ or f"toolu_{name}", name=name, input=args)


def msg(*content, stop="end_turn"):
    stop = "tool_use" if stop == "end_turn" and any(c.type == "tool_use" for c in content) else stop
    return SimpleNamespace(content=list(content), stop_reason=stop, usage=USAGE)


class FakeStream:
    def __init__(self, message):
        self.message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def __aiter__(self):
        for block in self.message.content:
            if block.type == "text":
                for word in block.text.split(" "):
                    yield SimpleNamespace(type="text", text=word + " ")

    async def get_final_message(self):
        return self.message


class FakeClient:
    def __init__(self, *script):
        self.script = list(script)
        self.calls = []
        self.beta = SimpleNamespace(messages=self)

    def stream(self, **params):
        self.calls.append({**params, "messages": list(params["messages"])})
        return FakeStream(self.script.pop(0))


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    assistant_client.set_client(None)


def use(*script) -> FakeClient:
    fake = FakeClient(*script)
    assistant_client.set_client(fake)
    return fake


def chat(client, message="Hi", *, context=None, headers=None, memories=None, history=()):
    body = {"messages": [*history, {"role": "user", "content": message}], "context": context or {"page": "home"}}
    if memories is not None:
        body["memories"] = memories
    resp = client.post("/api/assistant/chat", json=body, headers=headers or {})
    assert resp.status_code == 200, resp.text
    events = []
    for chunk in resp.text.strip().split("\n\n"):
        name, data = chunk.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def of(events, name):
    return [data for event, data in events if event == name]


def reply(events):
    return "".join(d["delta"] for d in of(events, "text")).strip()


def latest_user_text(call) -> str:
    return "\n".join(block["text"] for block in call["messages"][-1]["content"])


# ---------- Availability ----------

def test_disabled_without_api_key(client):
    assert client.get("/api/assistant/status").json()["enabled"] is False
    resp = client.post("/api/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 503


def test_status_enabled(client, enabled):
    assert client.get("/api/assistant/status").json() == {"enabled": True, "daily_limit": 40}


def test_rejects_bad_history(client, enabled):
    use()
    resp = client.post("/api/assistant/chat", json={"messages": [{"role": "assistant", "content": "hello"}]})
    assert resp.status_code == 422


def test_daily_limit(client, enabled, monkeypatch):
    monkeypatch.setenv("ASSISTANT_DAILY_LIMIT", "2")
    get_settings.cache_clear()
    use(msg(text("one")), msg(text("two")))
    chat(client)
    chat(client)
    resp = client.post("/api/assistant/chat", json={"messages": [{"role": "user", "content": "three"}]})
    assert resp.status_code == 429
    assert "2 assistant messages" in resp.json()["detail"]


# ---------- Conversation ----------

def test_text_reply_streams_with_context(client, enabled):
    fake = use(msg(text("Hello! How can I help?")))
    events = chat(client, "Hi there", history=[{"role": "user", "content": "earlier"},
                                               {"role": "assistant", "content": "earlier reply"}])
    assert reply(events) == "Hello! How can I help?"
    assert events[-1] == ("done", {})

    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "medium"}
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    # No resume open: no resume tools; jobs and memory tools only.
    assert [t["name"] for t in call["tools"]] == ["find_jobs", "get_job", "market_signal", "remember"]
    assert all(t["eager_input_streaming"] for t in call["tools"])
    # History is passed through; context rides only on the newest message.
    assert call["messages"][:2] == [{"role": "user", "content": "earlier"},
                                    {"role": "assistant", "content": "earlier reply"}]
    context = latest_user_text(call)
    assert context.startswith("<context>") and "Signed in: no" in context and "No resume is open" in context
    assert context.endswith("Hi there")


def test_legacy_model_skips_thinking_and_fallbacks(client, enabled, monkeypatch):
    monkeypatch.setenv("ASSISTANT_MODEL", "claude-haiku-4-5")
    get_settings.cache_clear()
    fake = use(msg(text("ok")))
    chat(client)
    assert {"thinking", "output_config", "fallbacks", "betas"}.isdisjoint(fake.calls[0])


def test_refusal_is_reported(client, enabled):
    use(msg(stop="refusal"))
    events = chat(client, "something disallowed")
    assert of(events, "error") == [{"message": "I can't help with that request."}]


def test_round_limit(client, enabled, monkeypatch):
    monkeypatch.setenv("ASSISTANT_MAX_ROUNDS", "2")
    get_settings.cache_clear()
    use(msg(tool("find_jobs", {}, "a")), msg(tool("find_jobs", {}, "b")))
    assert "Ask me to continue" in reply(chat(client, "jobs?"))


# ---------- Resume tools ----------

def builder_context(doc, **extra):
    return {"page": "builder", "document": doc, "editable": True, **extra}


def test_score_and_suggest_edits(client, enabled, sample_document):
    fake = use(
        msg(text("Let me check."), tool("score_resume", {}), tool("suggest_edits", {
            "note": "Lead with impact.",
            "edits": [
                {"kind": "replace_bullet", "experience_index": 0, "bullet_index": 1,
                 "text": "Migrated 30 dashboards to Power BI, saving the team 10 hours a week."},
                {"kind": "add_skills", "skills": ["SQL", "dbt"]},
                {"kind": "replace_bullet", "experience_index": 9, "bullet_index": 0, "text": "x"},
            ],
        })),
        msg(text("Done — apply the suggestions you like.")),
    )
    events = chat(client, "Improve my resume", context=builder_context(sample_document))

    assert [s["tool"] for s in of(events, "status")] == ["score_resume", "suggest_edits"]
    assert 0 < of(events, "score")[0]["ats_score"] <= 100
    [proposal] = of(events, "proposal")
    assert proposal["note"] == "Lead with impact."
    bullet, skills = proposal["edits"]
    assert bullet["label"] == "Data Analyst at Acme Corp · bullet 2"
    assert bullet["before"].startswith("Led migration of 30 dashboards")
    assert skills == {"kind": "add_skills", "label": "Skills", "before": "", "after": "dbt", "skills": ["dbt"]}
    assert reply(events) == "Let me check. \n\nDone — apply the suggestions you like."

    first, second = fake.calls
    assert [t["name"] for t in first["tools"]] == [
        "score_resume", "suggest_edits", "find_jobs", "get_job", "market_signal", "remember"]
    assert "[0.1] Led migration of 30 dashboards" in latest_user_text(first)
    results = second["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["toolu_score_resume", "toolu_suggest_edits"]
    assert results[0]["content"].startswith("ATS score:") and not results[0]["is_error"]
    assert "Skipped: Edit 3: Experience index 9 doesn't exist" in results[1]["content"]
    assert second["messages"][-2]["role"] == "assistant"


def test_invalid_tool_input_returns_error_result(client, enabled, sample_document):
    fake = use(msg(tool("suggest_edits", {"note": "x", "edits": []})), msg(text("Sorry.")))
    events = chat(client, "fix it", context=builder_context(sample_document))
    [result] = fake.calls[1]["messages"][-1]["content"]
    assert result["is_error"] and "Invalid input" in result["content"]
    assert not of(events, "proposal")


def test_edits_unavailable_when_read_only(client, enabled, sample_document):
    fake = use(msg(tool("suggest_edits", {"note": "x", "edits": [{"kind": "summary", "text": "New"}]})),
               msg(text("ok")))
    events = chat(client, "fix", context={"page": "scan", "document": sample_document})
    assert "suggest_edits" not in [t["name"] for t in fake.calls[0]["tools"]]
    assert fake.calls[1]["messages"][-1]["content"][0]["is_error"]
    assert not of(events, "proposal")


def test_render_resume_labels_indexes(sample_document):
    text_ = render_resume(ResumeDocument(**sample_document))
    assert "[0] Data Analyst — Acme Corp (2020-01 – present)" in text_
    assert "[1.0] Automated weekly sales reporting" in text_


# ---------- Jobs ----------

@pytest.fixture
def jobs(client, register):
    headers = register(ADMIN)
    for payload in (job_payload(), job_payload(title="Civil Site Engineer", company="BuildCo", discipline="civil",
                                               description="Supervise RCC construction sites and prepare BOQ.",
                                               skills=["AutoCAD"])):
        assert client.post("/api/admin/jobs", json=payload, headers=headers).status_code == 201
    return headers


def test_find_jobs_ranks_against_resume(client, enabled, jobs, sample_document):
    fake = use(msg(tool("find_jobs", {"limit": 2})), msg(text("Here you go.")))
    events = chat(client, "Recommend jobs", context=builder_context(sample_document))
    cards = of(events, "jobs")[0]["jobs"]
    assert cards[0]["title"] == "Data Analyst" and cards[0]["apply_url"] == "https://acme.example/careers/123"
    assert cards[0]["match_score"] > cards[1]["match_score"]
    assert "match" in fake.calls[1]["messages"][-1]["content"][0]["content"]


def test_find_and_get_job_without_resume(client, enabled, jobs):
    fake = use(msg(tool("find_jobs", {"query": "civil"})), msg(text("ok")))
    cards = of(chat(client, "civil jobs"), "jobs")[0]["jobs"]
    assert [c["title"] for c in cards] == ["Civil Site Engineer"] and "match_score" not in cards[0]

    fake = use(msg(tool("get_job", {"job_id": cards[0]["id"]})), msg(tool("get_job", {"job_id": "nope"})),
               msg(text("ok")))
    chat(client, "tell me more", context={"page": "job", "job_id": cards[0]["id"]})
    assert f'<viewing_job id="{cards[0]["id"]}">Civil Site Engineer at BuildCo' in latest_user_text(fake.calls[0])
    found = fake.calls[1]["messages"][-1]["content"][0]
    assert "<job_posting>" in found["content"] and "BOQ" in found["content"]
    assert fake.calls[2]["messages"][-1]["content"][0]["is_error"]


# ---------- Memory ----------

def test_signed_in_memory_persists(client, enabled, register):
    headers = register()
    use(msg(tool("remember", {"fact": "Targets junior data analyst roles in Dhaka"})), msg(text("Noted.")))
    events = chat(client, "I want data analyst jobs in Dhaka", headers=headers)
    assert of(events, "memory") == [{"fact": "Targets junior data analyst roles in Dhaka", "stored": "account"}]

    memories = client.get("/api/assistant/memories", headers=headers).json()
    assert [m["text"] for m in memories] == ["Targets junior data analyst roles in Dhaka"]

    fake = use(msg(text("hi")))
    chat(client, "hi again", headers=headers, memories=["ignored for signed-in users"])
    context = latest_user_text(fake.calls[0])
    assert "- Targets junior data analyst roles in Dhaka" in context and "ignored" not in context

    assert client.delete(f"/api/assistant/memories/{memories[0]['id']}", headers=headers).status_code == 204
    assert client.get("/api/assistant/memories", headers=headers).json() == []


def test_memory_cap_drops_oldest(client, enabled, register, monkeypatch):
    monkeypatch.setenv("ASSISTANT_MAX_MEMORIES", "2")
    get_settings.cache_clear()
    headers = register()
    use(*[m for i in range(3) for m in (msg(tool("remember", {"fact": f"fact number {i}"})), msg(text("ok")))])
    for i in range(3):
        chat(client, f"remember {i}", headers=headers)
    assert sorted(m["text"] for m in client.get("/api/assistant/memories", headers=headers).json()) == [
        "fact number 1", "fact number 2"]


def test_signed_out_memory_stays_in_browser(client, enabled):
    fake = use(msg(tool("remember", {"fact": "Prefers remote work"})), msg(text("ok")))
    events = chat(client, "I like remote", memories=["Studies civil engineering"])
    assert of(events, "memory") == [{"fact": "Prefers remote work", "stored": "browser"}]
    assert "- Studies civil engineering" in latest_user_text(fake.calls[0])
    with get_session_factory()() as db:
        assert db.scalars(select(AssistantMemory)).all() == []


def test_memories_require_sign_in(client):
    assert client.get("/api/assistant/memories").status_code == 401


# ---------- Job descriptions ----------

DRAFT = {"title": "Business Analyst", "company": "Prottoy Labs", "discipline": "data", "workplace": "hybrid",
         "location": "Dhaka", "description": "Gather requirements, write user stories and analyse data in SQL.",
         "skills": ["SQL", "Jira"], "salary_min": 60000, "salary_max": 90000}


def test_admin_can_save_job_draft(client, enabled, register):
    headers = register(ADMIN)
    fake = use(msg(tool("save_job_draft", DRAFT)), msg(text("Saved as a draft.")))
    events = chat(client, "Write a JD for a business analyst and save it", headers=headers,
                  context={"page": "admin"})
    assert "save_job_draft" in [t["name"] for t in fake.calls[0]["tools"]]
    [draft] = of(events, "job_draft")
    with get_session_factory()() as db:
        job = db.get(Job, draft["id"])
        assert (job.status, job.source, job.salary_currency) == ("draft", "local", "BDT")
    assert client.get("/api/jobs").json()["total"] == 0  # drafts aren't public


def test_non_admin_cannot_save_job_draft(client, enabled, register):
    fake = use(msg(tool("save_job_draft", DRAFT)), msg(text("ok")))
    events = chat(client, "save a job", headers=register())
    assert "save_job_draft" not in [t["name"] for t in fake.calls[0]["tools"]]
    result = fake.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] and "isn't available" in result["content"]
    assert not of(events, "job_draft")


def test_invalid_job_draft_reports_errors(client, enabled, register):
    fake = use(msg(tool("save_job_draft", {**DRAFT, "description": "too short"})), msg(text("ok")))
    chat(client, "save", headers=register(ADMIN))
    result = fake.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] and "description" in result["content"]
