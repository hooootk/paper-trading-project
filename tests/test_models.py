"""Tests for data models."""

from paper_trading.models import Order, Position, Portfolio


def test_order_creation() -> None:
    """Verify Order model instantiation."""
    order = Order(symbol="AAPL", quantity=10, price=150.0, side="buy")
    assert order.symbol == "AAPL"
    assert order.quantity == 10
    assert order.price == 150.0
    assert order.side == "buy"


def test_position_creation() -> None:
    """Verify Position model instantiation."""
    position = Position(symbol="AAPL", quantity=10, average_price=150.0)
    assert position.symbol == "AAPL"
    assert position.quantity == 10


def test_portfolio_defaults() -> None:
    """Verify Portfolio model defaults."""
    portfolio = Portfolio()
    assert portfolio.cash == 0.0
    assert portfolio.positions == []
