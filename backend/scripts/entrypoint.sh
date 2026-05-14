#!/bin/sh
set -e

echo "Running database migrations..."
alembic -c /app/migrations/alembic.ini upgrade head
echo "Migrations complete."

exec "$@"
