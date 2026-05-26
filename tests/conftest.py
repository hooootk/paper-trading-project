"""Pytest configuration and shared fixtures."""

import pytest

from paper_trading.models import Order, Position


@pytest.fixture
def sample_order() -> Order:
    """Create a sample buy order for testing."""
    return Order(symbol="AAPL", quantity=10, price=150.0, side="buy")


@pytest.fixture
def sample_position() -> Position:
    """Create a sample position for testing."""
    return Position(symbol="AAPL", quantity=10, average_price=150.0)
