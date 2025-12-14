#!/bin/bash

# Run tests with coverage

set -e

echo "=== Installing test dependencies ==="
pip install -q -r requirements-dev.txt

echo -e "\n=== Creating test database ==="
# Create test database if it doesn't exist
docker compose exec -T postgres psql -U postgres -c "DROP DATABASE IF EXISTS pat_test;" || true
docker compose exec -T postgres psql -U postgres -c "CREATE DATABASE pat_test;" || true

echo -e "\n=== Running tests ==="
pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

echo -e "\n=== Test Summary ==="
echo "Coverage report: htmlcov/index.html"
