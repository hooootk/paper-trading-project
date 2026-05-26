"""Tests for main module."""

from paper_trading.main import main_cli


def test_main_imports() -> None:
    """Verify main_cli is importable."""
    assert callable(main_cli)
