#!/bin/bash
# Initialize ARIE database
set -e
if [ -z "$DATABASE_URL" ]; then
  export DATABASE_URL="postgresql://arie:arie@localhost:5432/arie"
fi
psql "$DATABASE_URL" -f "$(dirname "$0")/schema.sql"
echo "Database initialized successfully."
