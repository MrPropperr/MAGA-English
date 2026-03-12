#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "Starting Redis..."
docker compose -f docker-compose.dev.yml up -d

echo "Waiting for Redis..."
until docker compose -f docker-compose.dev.yml exec redis redis-cli ping 2>/dev/null | grep -q PONG; do
    sleep 0.5
done
echo "Redis is ready."

echo "Starting bot..."
python -m bot.main
