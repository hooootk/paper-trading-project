"""Application configuration using pydantic-settings."""

from functools import lru_cache

from openai import AzureOpenAI
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Paper Trading Project"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    # Azure OpenAI
    azure_openai_endpoint: str = "https://hkust.azure-api.net/"
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2025-02-01-preview"
    azure_openai_deployment: str = "gpt-4o"

    # Alpaca Paper Trading
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # Trading params
    lookback_days: int = 20
    backtest_start: str = "2022-01-01"
    initial_capital: int = 100_000
    take_profit_pct: float = 0.15
    stop_loss_pct: float = 0.08
    trailing_stop_pct: float = 0.05
    risk_free_rate: float = 0.04

    # Portfolio
    portfolio_tickers: str = "AAPL,MSFT,JPM,JNJ,XOM,AMZN,NVDA,UNH,BAC,PG"

    model_config = {"env_prefix": "PAPER_TRADING_", "env_file": ".env"}

    def get_portfolio_tickers(self) -> list[str]:
        return [t.strip() for t in self.portfolio_tickers.split(",") if t.strip()]


settings = Settings()


@lru_cache(maxsize=1)
def get_azure_client() -> AzureOpenAI:
    """Get or create the shared Azure OpenAI client (cached singleton)."""
    return AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )
