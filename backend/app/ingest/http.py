"""A deliberately polite HTTP client for ingestion.

- Identifies itself (User-Agent with a contact URL) instead of pretending to
  be a browser.
- At most one request per host every `min_delay` seconds.
- Retries 429/5xx a couple of times, honouring Retry-After.
- For scraping sources, checks robots.txt before every URL and refuses what
  it disallows. If robots.txt can't be read (network error or 5xx), the host
  is treated as disallowed — failing closed, not open. A 404 robots.txt means
  "no rules", per the robots exclusion standard (RFC 9309).
"""

import asyncio
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "ProttoyBot/1.0 (+https://atikul-dipto.github.io/ats-resume-scanner/; job aggregator; honours robots.txt)"
ROBOTS_AGENT = "ProttoyBot"
TIMEOUT = 20.0
RETRIES = 2


class RobotsDisallowed(Exception):
    pass


class PoliteClient:
    def __init__(self, client: httpx.AsyncClient, min_delay: float = 2.0):
        self._client = client
        self._min_delay = min_delay
        self._last: dict[str, float] = {}
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self.requests = 0

    async def _throttle(self, host: str) -> None:
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = self._last.get(host, 0) + self._min_delay - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last[host] = time.monotonic()

    async def _robots_for(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = RobotFileParser()
            try:
                resp = await self._raw_get(f"{origin}/robots.txt")
            except httpx.HTTPError:
                self._robots[origin] = None
                return None
            if resp.status_code >= 500 or resp.status_code in (401, 403):
                parser = None  # can't tell what's allowed: treat as disallowed
            elif resp.status_code >= 400:
                parser.parse([])  # no robots.txt: everything allowed
            else:
                parser.parse(resp.text.splitlines())
            self._robots[origin] = parser
        return self._robots[origin]

    async def allowed(self, url: str) -> bool:
        parser = await self._robots_for(url)
        return parser is not None and parser.can_fetch(ROBOTS_AGENT, url)

    async def _raw_get(self, url: str, **kwargs) -> httpx.Response:
        host = urlsplit(url).netloc
        for attempt in range(RETRIES + 1):
            await self._throttle(host)
            self.requests += 1
            resp = await self._client.get(
                url, headers={"User-Agent": USER_AGENT, **kwargs.pop("headers", {})},
                timeout=TIMEOUT, follow_redirects=True, **kwargs,
            )
            if resp.status_code in (429, 502, 503, 504) and attempt < RETRIES:
                retry_after = resp.headers.get("Retry-After", "")
                await asyncio.sleep(min(float(retry_after), 60) if retry_after.isdigit() else 2 ** (attempt + 1))
                continue
            return resp
        return resp

    async def get(self, url: str, *, check_robots: bool, **kwargs) -> httpx.Response:
        if check_robots and not await self.allowed(url):
            raise RobotsDisallowed(url)
        resp = await self._raw_get(url, **kwargs)
        resp.raise_for_status()
        return resp
