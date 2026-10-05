"""CLI: ingest jobs from every configured source.

    python -m app.ingest.run                       # all enabled sources, writes to DATABASE_URL
    python -m app.ingest.run --dry-run             # fetch + filter + report, write nothing
    python -m app.ingest.run --source canonical --keyword data --report out.json

Scheduled by .github/workflows/ingest.yml (GitHub's runners have open
internet; the API container doesn't need to do this work).
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

import httpx
import yaml

from app.ingest.http import PoliteClient
from app.ingest.models import IngestConfig
from app.ingest.pipeline import run_source
from app.jobs.catalog_sync import fetch_external, upsert_external

DEFAULT_CONFIG = Path(__file__).with_name("sources.yaml")
logger = logging.getLogger("app.ingest")


def load_config(path: Path = DEFAULT_CONFIG) -> IngestConfig:
    return IngestConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


async def run(cfg: IngestConfig, *, only: list[str] | None = None, dry_run: bool = False,
              keywords: list[str] | None = None, http: httpx.AsyncClient | None = None) -> dict:
    started = time.monotonic()
    reports = []
    async with (http or httpx.AsyncClient()) as raw_client:
        client = PoliteClient(raw_client, min_delay=cfg.min_delay_seconds)
        for src in cfg.sources:
            if only and src.name not in only:
                continue
            if src.type == "public_apis":
                if not src.enabled:
                    reports.append({"source": src.name, "type": src.type, "status": "disabled"})
                    continue
                raw = await fetch_external(raw_client)
                report = {"source": src.name, "type": src.type, "status": "ok", "fetched": len(raw)}
                if not dry_run:
                    report.update(await asyncio.get_running_loop().run_in_executor(None, upsert_external, raw))
                reports.append(report)
                continue
            report = await run_source(client, cfg, src, dry_run=dry_run, extra_keywords=keywords)
            logger.info("%s", json.dumps(report, default=str))
            reports.append(report)
    return {
        "dry_run": dry_run,
        "seconds": round(time.monotonic() - started, 1),
        "requests": client.requests,
        "kept": sum(r.get("kept", 0) for r in reports),
        "created": sum(r.get("created", 0) for r in reports),
        "sources": reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--source", action="append", help="only run this source (repeatable)")
    parser.add_argument("--keyword", action="append", help="extra title keyword filter (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="fetch and filter, but don't write")
    parser.add_argument("--report", type=Path, help="write the JSON report here")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    summary = asyncio.run(run(load_config(args.config), only=args.source, dry_run=args.dry_run, keywords=args.keyword))
    text = json.dumps(summary, indent=2, default=str)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text)
    failed = [r for r in summary["sources"] if r.get("status") == "error"]
    # Partial failure is normal (a board moves, an API blips): only fail the
    # run when nothing worked at all, so one bad source doesn't page anyone.
    return 1 if failed and len(failed) == len([r for r in summary["sources"] if r.get("status") != "disabled"]) else 0


if __name__ == "__main__":
    sys.exit(main())
