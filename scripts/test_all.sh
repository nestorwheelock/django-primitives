#!/bin/bash
# Run tests for all packages

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================"
echo "  DJANGO-PRIMITIVES TEST SUITE"
echo "========================================"
echo

failed=0
for pkg in "$ROOT_DIR"/packages/*/; do
    name=$(basename "$pkg")
    echo "========================================"
    echo "Testing: $name"
    echo "========================================"

    if pytest "$pkg" -v --tb=short; then
        echo "  $name: PASS"
    else
        echo "  $name: FAIL"
        failed=1
    fi
    echo
done

echo "========================================"
if [ $failed -eq 0 ]; then
    echo "All packages passed!"
    exit 0
else
    echo "Some packages failed. See above for details."
    exit 1
fi
