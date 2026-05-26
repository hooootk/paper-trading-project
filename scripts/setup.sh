#!/usr/bin/env bash
set -euo pipefail

echo "Setting up Paper Trading Project..."

# Create virtual environment
python -m venv .venv

# Activate and install
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
pip install -e ".[dev]"

# Copy env template if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || echo "No .env.example found, skipping."
fi

echo "Setup complete! Activate with: source .venv/bin/activate"
