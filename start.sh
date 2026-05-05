#!/usr/bin/env bash
set -e

SERVICE=$1

echo "Starting Shopee Agent Service: ${SERVICE}"

# Apply migrations if necessary
# alembic upgrade head

if [ "$SERVICE" = "api" ]; then
    echo "Running REST API server on port 8000"
    exec uvicorn shopee_agent.entrypoints.api.main:app --host 0.0.0.0 --port 8000
elif [ "$SERVICE" = "bot" ]; then
    echo "Running Telegram Bot"
    exec python -m shopee_agent.entrypoints.telegram.main
elif [ "$SERVICE" = "worker" ]; then
    echo "Running Background Worker"
    # Simple loop for the worker if it doesn't loop internally
    while true; do
        python -c "
from shopee_agent.entrypoints.worker.main import run_once
import time
import sys

try:
    did_work = run_once()
    if not did_work:
        time.sleep(5)
except Exception as e:
    print(f'Worker error: {e}', file=sys.stderr)
    time.sleep(10)
"
    done
else:
    echo "Unknown service type: $SERVICE"
    echo "Available services: api, bot, worker"
    exit 1
fi
