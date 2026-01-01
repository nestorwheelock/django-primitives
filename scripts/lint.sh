#!/bin/bash
# Run all boundary and architecture checks

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================"
echo "  DJANGO-PRIMITIVES LINT CHECKS"
echo "========================================"
echo

# Layer boundary check via django-layers
echo "Checking layer boundaries..."
PYTHONPATH="$ROOT_DIR/packages/django-layers/src" \
    python -m django_layers.cli check \
    --config "$ROOT_DIR/layers.yaml" \
    --root "$ROOT_DIR/packages" \
    --format text

echo
echo "Checking BaseModel usage..."
python "$ROOT_DIR/scripts/check_basemodel.py"

echo
echo "========================================"
echo "All checks passed!"
