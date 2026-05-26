"""Utility functions."""

import logging

logger = logging.getLogger(__name__)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def format_currency(amount: float, decimals: int = 2) -> str:
    """Format a float as a currency string."""
    return f"${amount:,.{decimals}f}"
