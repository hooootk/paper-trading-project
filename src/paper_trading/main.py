"""Application entry point.

Can be run as:
    python -m paper_trading
    python src/paper_trading/main.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly
_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from paper_trading.cli import main_cli

if __name__ == "__main__":
    main_cli()
