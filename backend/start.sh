#!/bin/sh
# Container entrypoint: migrate, then serve.
#
# Running migrations here is right for a single instance (the free tier).
# Once there are several instances, move `alembic upgrade head` to a
# one-off release/pre-deploy job so instances don't race to migrate.
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic upgrade head
fi

# --proxy-headers: the platform's load balancer terminates TLS; trust its
# X-Forwarded-For so rate limits key on the real client IP, not the proxy's.
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips "*" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --no-server-header
