#!/bin/sh
set -e

echo "Running database migrations..."
if alembic -c /app/migrations/alembic.ini upgrade head; then
    echo "Migrations complete."
else
    echo "WARNING: Migrations failed — starting server anyway. Check DB connectivity."
fi

exec "$@"
