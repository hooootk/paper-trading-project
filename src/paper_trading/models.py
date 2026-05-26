"""Data models for the paper trading application."""

from pydantic import BaseModel


class Order(BaseModel):
    """Trading order model."""

    symbol: str
    quantity: int
    price: float
    side: str  # "buy" or "sell"


class Position(BaseModel):
    """Portfolio position model."""

    symbol: str
    quantity: int
    average_price: float


class Portfolio(BaseModel):
    """User portfolio model."""

    cash: float = 0.0
    positions: list[Position] = []
