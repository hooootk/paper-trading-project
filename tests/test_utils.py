"""Tests for utility functions."""

import pytest

from paper_trading.utils import safe_divide, format_currency


def test_safe_divide_normal() -> None:
    """Verify safe_divide with valid inputs."""
    assert safe_divide(10.0, 2.0) == 5.0


def test_safe_divide_by_zero() -> None:
    """Verify safe_divide returns default when dividing by zero."""
    assert safe_divide(10.0, 0.0) == 0.0
    assert safe_divide(10.0, 0.0, default=-1.0) == -1.0


def test_format_currency() -> None:
    """Verify currency formatting."""
    assert format_currency(1000.5) == "$1,000.50"
    assert format_currency(0) == "$0.00"
