"""The AI assistant: a streamed chat (server-sent events) plus the user's
saved memories. Disabled, and hidden by the UI, until ANTHROPIC_API_KEY is set."""

import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.assistant.agent import run_turn
from app.assistant.prompt import build_context
from app.assistant.tools import ToolContext
from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.db.models import AssistantMemory, Job
from app.jobs.catalog import open_condition
from app.schemas.assistant import ChatRequest, MemoryOut

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/status")
def assistant_status():
    settings = get_settings()
    return {"enabled": settings.assistant_enabled, "daily_limit": settings.assistant_daily_limit}


async def _check_daily_limit(request: Request, user_id: str | None) -> None:
    settings = get_settings()
    who = f"u:{user_id}" if user_id else f"ip:{request.client.host if request.client else 'unknown'}"
    day = int(time.time()) // 86400
    count = await get_cache().incr(f"assistant:day:{who}:{day}", ttl_seconds=86400)
    if count > settings.assistant_daily_limit:
        raise HTTPException(429, f"You've used today's {settings.assistant_daily_limit} assistant messages. "
                                 "They reset at midnight UTC.")


def _sse(event: dict) -> str:
    return f"event: {event['event']}\ndata: {json.dumps(event['data'], default=str)}\n\n"


@router.post("/chat", dependencies=[Depends(rate_limit("assistant"))])
async def chat(body: ChatRequest, request: Request, user: OptionalUser, db: DbSession):
    settings = get_settings()
    if not settings.assistant_enabled:
        raise HTTPException(503, "The assistant isn't available right now.")
    await _check_daily_limit(request, user.id if user else None)

    # Everything the stream needs is read now, as plain values: the request's
    # DB session isn't used once streaming starts.
    ctx_in = body.context
    if user is not None:
        memories = list(db.scalars(select(AssistantMemory.text).where(AssistantMemory.user_id == user.id)
                                   .order_by(AssistantMemory.created_at)))
    else:
        memories = list(dict.fromkeys(m for m in body.memories if m))
    job = None
    if ctx_in.job_id:
        row = db.scalar(select(Job).where(Job.id == ctx_in.job_id, open_condition()))
        job = {"id": row.id, "title": row.title, "company": row.company} if row else None

    is_admin = bool(user and user.is_admin)
    context = build_context(
        page=ctx_in.page, signed_in=user is not None, is_admin=is_admin, memories=memories,
        document=ctx_in.document, editable=ctx_in.editable, job_description=ctx_in.job_description, job=job,
    )
    *history, latest = body.messages
    messages = [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": [
        {"type": "text", "text": context},
        {"type": "text", "text": latest.content},
    ]})
    tool_ctx = ToolContext(
        user_id=user.id if user else None, is_admin=is_admin, document=ctx_in.document,
        editable=ctx_in.editable and ctx_in.document is not None, job_description=ctx_in.job_description,
        max_memories=settings.assistant_max_memories,
    )

    async def stream() -> AsyncIterator[str]:
        async for event in run_turn(messages, tool_ctx):
            yield _sse(event)
        yield _sse({"event": "done", "data": {}})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/memories", response_model=list[MemoryOut])
def list_memories(user: CurrentUser, db: DbSession):
    rows = db.scalars(select(AssistantMemory).where(AssistantMemory.user_id == user.id)
                      .order_by(AssistantMemory.created_at)).all()
    return [{"id": m.id, "text": m.text} for m in rows]


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(memory_id: str, user: CurrentUser, db: DbSession):
    db.execute(delete(AssistantMemory).where(AssistantMemory.id == memory_id, AssistantMemory.user_id == user.id))
    db.commit()


@router.delete("/memories", status_code=status.HTTP_204_NO_CONTENT)
def clear_memories(user: CurrentUser, db: DbSession):
    db.execute(delete(AssistantMemory).where(AssistantMemory.user_id == user.id))
    db.commit()
