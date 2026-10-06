"""The agent loop: stream Claude's reply, run the tools it calls, repeat.

Yields browser events ({"event": name, "data": {...}}): text deltas, a status
line while a tool runs, and the tools' own events (job cards, edit
suggestions, saved memories). The conversation itself is stateless: the
browser sends the visible history back each time, and each request appends
to its own copy only, so nothing earlier in the conversation is rewritten.
"""

import logging
from collections.abc import AsyncIterator

import anthropic

from app.assistant.client import get_client
from app.assistant.prompt import SYSTEM_PROMPT
from app.assistant.tools import ToolContext, run_tool, tools_for
from app.core.config import get_settings

logger = logging.getLogger("app.assistant")

# Server-side fallback when a model's safety classifier declines a request:
# "default" routes by refusal category to Anthropic's recommended model.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = ("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")
# Models without adaptive thinking / effort.
LEGACY_MODELS = ("claude-haiku-4-5",)
MAX_JSON_RETRIES = 2

STATUS = {
    "score_resume": "Scoring your resume",
    "suggest_edits": "Preparing suggestions",
    "find_jobs": "Searching jobs",
    "get_job": "Reading the job posting",
    "market_signal": "Reading the job market",
    "remember": "Remembering that",
    "save_job_draft": "Saving the job draft",
}


def request_params(tools: list[dict]) -> dict:
    settings = get_settings()
    model = settings.assistant_model
    params = {
        "model": model,
        "max_tokens": settings.assistant_max_tokens,
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        "tools": tools,
    }
    if not model.startswith(LEGACY_MODELS):
        params["thinking"] = {"type": "adaptive"}
        params["output_config"] = {"effort": settings.assistant_effort}
    if model.startswith(FALLBACK_MODELS):
        params["betas"] = [FALLBACK_BETA]
        params["fallbacks"] = "default"
    return params


def _error(message: str) -> dict:
    return {"event": "error", "data": {"message": message}}


async def run_turn(messages: list[dict], ctx: ToolContext) -> AsyncIterator[dict]:
    settings = get_settings()
    params = request_params(tools_for(ctx))
    convo = list(messages)
    wrote_text = False
    json_retries = 0
    usage = {"input": 0, "output": 0, "cache_read": 0, "rounds": 0}

    round_no = 0
    while round_no < settings.assistant_max_rounds:
        round_no += 1
        new_round = True
        try:
            async with get_client().beta.messages.stream(**params, messages=convo) as stream:
                async for event in stream:
                    if event.type == "text" and event.text:
                        if new_round and wrote_text:
                            yield {"event": "text", "data": {"delta": "\n\n"}}
                        new_round = False
                        wrote_text = True
                        yield {"event": "text", "data": {"delta": event.text}}
                message = await stream.get_final_message()
            json_retries = 0
        except ValueError:
            # Tool input the SDK couldn't parse at all; no tool_use id to answer, so re-ask.
            json_retries += 1
            if json_retries > MAX_JSON_RETRIES:
                yield _error("Something went wrong preparing that. Please try again.")
                return
            continue
        except anthropic.RateLimitError:
            yield _error("The assistant is busy right now. Please try again in a minute.")
            return
        except anthropic.AuthenticationError:
            logger.error("assistant: Anthropic rejected the API key")
            yield _error("The assistant isn't set up correctly. Please let the site admin know.")
            return
        except anthropic.APIStatusError as exc:
            logger.warning("assistant: API error %s (request %s)", exc.status_code, exc.request_id)
            yield _error("The assistant ran into a problem. Please try again.")
            return
        except anthropic.APIConnectionError:
            yield _error("Couldn't reach the AI service. Please try again.")
            return

        usage["rounds"] += 1
        if message.usage is not None:
            usage["input"] += message.usage.input_tokens or 0
            usage["output"] += message.usage.output_tokens or 0
            usage["cache_read"] += getattr(message.usage, "cache_read_input_tokens", 0) or 0

        if message.stop_reason == "refusal":
            yield _error("I can't help with that request.")
            break
        if message.stop_reason == "pause_turn":
            convo.append({"role": "assistant", "content": message.content})
            continue
        tool_uses = [b for b in message.content if b.type == "tool_use"]
        if not tool_uses:
            if message.stop_reason == "max_tokens":
                yield {"event": "text", "data": {"delta": "…"}}
            break
        if message.stop_reason == "max_tokens":
            # A tool input cut off mid-way still parses; don't run it.
            yield _error("That reply ran too long. Try asking for something smaller.")
            break

        convo.append({"role": "assistant", "content": message.content})
        results = []
        for block in tool_uses:
            yield {"event": "status", "data": {"tool": block.name, "label": STATUS.get(block.name, "Working")}}
            ctx.events.clear()
            content, is_error = await run_tool(ctx, block.name, block.input)
            for event in ctx.events:
                yield event
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error})
        # All results in one user turn, so parallel tool calls stay parallel.
        convo.append({"role": "user", "content": results})
    else:
        yield {"event": "text", "data": {"delta": "\n\n(I stopped there to keep this short. Ask me to continue.)"}}

    logger.info("assistant turn: model=%s rounds=%d input=%d cache_read=%d output=%d", params["model"],
                usage["rounds"], usage["input"], usage["cache_read"], usage["output"])
