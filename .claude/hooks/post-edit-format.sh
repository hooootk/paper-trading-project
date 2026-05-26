#!/usr/bin/env bash
set -euo pipefail

echo "Running post-edit format..."

# Auto-format modified Python files
ruff format .

echo "Formatting complete."
