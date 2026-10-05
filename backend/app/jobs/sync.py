"""CLI: refresh the job catalog from the public job APIs.

    cd backend && python -m app.jobs.sync

Schedule this (Render cron job, GitHub Actions `schedule:`) once the API runs
on more than one instance, and set JOBS_SYNC_ENABLED=false on web instances.
"""

import asyncio
import json
import logging

from app.jobs.catalog_sync import sync_external_jobs

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(asyncio.run(sync_external_jobs())))
