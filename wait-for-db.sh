#!/bin/sh
set -e

echo "⏳ Waiting for database at $DATABASE_URL..."

# Extract host and port from DATABASE_URL (works with postgresql:// or postgresql+psycopg2://)
DB_HOST=$(echo "$DATABASE_URL" | sed -E 's/^.*:\/\/.*:.*@(.*):[0-9]+\/.*$/\1/')
DB_PORT=$(echo "$DATABASE_URL" | sed -E 's/^.*:\/\/.*:([0-9]+)\/.*$/\1/')

until nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 1
done

echo "✅ Database is up — running migrations..."
poetry run alembic upgrade head

echo "🚀 Starting FastAPI..."
exec poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
