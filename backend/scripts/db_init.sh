#!/bin/bash
set -e

echo "Waiting for SQL Server to be ready..."

python - <<'PYEOF'
import pyodbc, os, time, sys

server   = os.environ["AZURE_SQL_SERVER"]
database = os.environ["AZURE_SQL_DATABASE"]
username = os.environ["AZURE_SQL_USERNAME"]
password = os.environ["AZURE_SQL_PASSWORD"]

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={server};"
    f"UID={username};"
    f"PWD={password};"
    "TrustServerCertificate=yes"
)

for attempt in range(15):
    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
        conn.execute(
            f"IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name='{database}') "
            f"CREATE DATABASE [{database}]"
        )
        conn.close()
        print(f"Database '{database}' ready.")
        sys.exit(0)
    except Exception as exc:
        print(f"Attempt {attempt + 1}/15: waiting for SQL Server... {exc}")
        time.sleep(5)

print("ERROR: SQL Server not reachable after 15 attempts.")
sys.exit(1)
PYEOF

echo "Running Alembic migrations..."
alembic -c migrations/alembic.ini upgrade head
echo "DB init complete."
