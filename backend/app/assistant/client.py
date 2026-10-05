"""The one Anthropic client for the process. Tests swap in a fake."""

import anthropic

from app.core.config import get_settings

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key, timeout=120.0, max_retries=2)
    return _client


def set_client(client) -> None:
    global _client
    _client = client
