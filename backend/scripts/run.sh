#!/bin/bash
# Run all setup steps in one go

set -e
cd "$(dirname "$0")/.."

echo "======================================"
echo "  AML System — Backend Setup"
echo "======================================"

# Create venv if not exists
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt --quiet

echo "[1/3] Seeding database..."
python scripts/seed_data.py

echo "[2/3] Importing OFAC sanctions list..."
python scripts/import_sanctions.py

echo "[3/3] Starting API server..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000
