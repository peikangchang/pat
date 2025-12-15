#!/bin/bash

# PAT API Test Runner
# Runs tests in two separate phases to avoid rate limiting conflicts

set -e  # Exit on error

echo "=================================="
echo "PAT API Test Suite"
echo "=================================="
echo ""

# Phase 1: Main tests (excluding rate limiting)
echo "Phase 1: Running main tests (173 tests)..."
echo "----------------------------------"
pytest tests/ --ignore=tests/test_rate_limiting.py -v --tb=short
MAIN_EXIT=$?

echo ""
echo "Phase 1 completed with exit code: $MAIN_EXIT"
echo ""

# Phase 2: Rate limiting tests
echo "Phase 2: Running rate limiting tests (12 tests)..."
echo "----------------------------------"
pytest tests/test_rate_limiting.py -v --tb=short
RATE_EXIT=$?

echo ""
echo "Phase 2 completed with exit code: $RATE_EXIT"
echo ""

# Summary
echo "=================================="
echo "Test Summary"
echo "=================================="
if [ $MAIN_EXIT -eq 0 ] && [ $RATE_EXIT -eq 0 ]; then
    echo "✓ All tests passed!"
    echo "  - Main tests: PASSED (173 tests)"
    echo "  - Rate limiting tests: PASSED (12 tests)"
    echo "  - Total: 185 tests, 100% pass rate"
    exit 0
else
    echo "✗ Some tests failed"
    [ $MAIN_EXIT -ne 0 ] && echo "  - Main tests: FAILED"
    [ $RATE_EXIT -ne 0 ] && echo "  - Rate limiting tests: FAILED"
    exit 1
fi
