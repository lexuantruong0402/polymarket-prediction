"""Bot-wide configuration loaded from environment / .env file."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/predict_market_bot/config/settings.py -> root is 4 levels up
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class BotSettings(BaseSettings):
    """Central configuration — every value can be overridden via env vars."""

    # ── API ──────────────────────────────────────────────────────────────
    api_base_url: str = Field(
        "https://gamma-api.polymarket.com",
        description="Polymarket Gamma API base URL (market listing)",
    )
    clob_api_url: str = Field(
        "https://clob.polymarket.com",
        description="Polymarket CLOB API base URL (pricing & trading)",
    )
    api_key: str = Field("", description="API key for authenticated endpoints")
    news_api_key: str | None = Field(
        None, description="API key for newsapi.org"
    )
    openai_api_key: str | None = Field(
        None, description="Optional API key for LLM-based sentiment"
    )
    gemini_api_key: str | None = Field(
        None, description="Google Gemini API key for calibration"
    )
    model_path: str = Field(
        "data/models/xgboost_market_v1.json",
        description="Path to the trained XGBoost model file",
    )


    # ── Portfolio ────────────────────────────────────────────────────────
    bankroll: float = Field(10_000.0, gt=0, description="Total capital available")
    max_exposure: float = Field(0.30, gt=0, le=1.0, description="Max fraction of bankroll exposed")
    kelly_alpha: float = Field(0.25, gt=0, le=1.0, description="Fractional Kelly multiplier")

    # ── Risk Limits ─────────────────────────────────────────────────────
    edge_threshold: float = Field(0.04, ge=0, description="Min edge to consider a trade")
    mdd_limit: float = Field(0.08, gt=0, le=1.0, description="Max drawdown limit")
    var_limit_daily: float = Field(500.0, gt=0, description="Daily VaR cap in currency")
    confidence_threshold: float = Field(0.60, gt=0, le=1.0, description="Min prediction confidence")

    # ── Scanner ─────────────────────────────────────────────────────────
    min_liquidity: float = Field(5_000.0, ge=0, description="Min market liquidity to pass scan")
    min_volume: float = Field(1_000.0, ge=0, description="Min 24h volume to pass scan")
    scan_limit: int = Field(300, gt=0, description="Max markets to fetch per scan")
    exclude_tag_id: int | None = Field(1312, description="Tag ID to exclude from scan (e.g. 1312)")

    # ── Logging ─────────────────────────────────────────────────────────
    log_level: str = Field("INFO", description="Logging level")
    log_format: str = Field("json", description="Log output format (json | console)")

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Singleton — import and use directly
settings = BotSettings()
