"""Configuration: tunables from config.yaml + secrets from environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional at runtime (e.g. in CI, secrets are real env vars)
    pass


# ----- config.yaml schema -----------------------------------------------------


class Window(BaseModel):
    # Only upcoming releases are shown, so there is no "past" side — just how far ahead to look.
    future_days: int = 42


class Fees(BaseModel):
    commission_pct: float = 0.09
    payment_processing_pct: float = 0.03
    shipping_cost: float = 0.0

    @property
    def total_pct(self) -> float:
        return self.commission_pct + self.payment_processing_pct


class Thresholds(BaseModel):
    min_profit: float = 40.0
    min_margin: float = 0.20
    # Recent sales required to consider a pair liquid. Default 0 (off): new/upcoming
    # releases have no sales history yet, so this would otherwise hide every result.
    min_sales_count: int = 0


class ApiConfig(BaseModel):
    base_url: str = "https://api.kicks.dev/v3"
    market: str = "US"  # pricing market, e.g. US, DE, EU (see KicksDB market enum)
    page_limit: int = 50
    max_pages: int = 4
    request_timeout_seconds: int = 30


class Config(BaseModel):
    brands: List[str] = Field(default_factory=lambda: ["Nike", "Jordan"])
    window: Window = Field(default_factory=Window)
    fees: Fees = Field(default_factory=Fees)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    resale_signal: str = "lowest_ask"  # "lowest_ask" or "average"
    sort_by: str = "profit"            # "profit" (desc) or "date" (soonest first)
    max_results: int = 25
    api: ApiConfig = Field(default_factory=ApiConfig)


# ----- secrets ----------------------------------------------------------------


class Secrets(BaseModel):
    kicksdb_api_key: str
    gmail_address: str
    gmail_app_password: str
    recipient_email: str
    # Supabase target for the web-platform refresh job. Optional for the email path
    # (only required by `refresh.py`, where require_supabase=True).
    supabase_url: str = ""
    supabase_service_key: str = ""


def load_config(path: str | Path = "config.yaml") -> Config:
    path = Path(path)
    if not path.exists():
        return Config()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Config.model_validate(data)


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            f"Copy .env.example to .env (local) or set it as a GitHub Secret (CI)."
        )
    return val


def load_secrets(require_email: bool = True, require_supabase: bool = False) -> Secrets:
    """Load secrets from the environment.

    When `require_email` is False (e.g. --dry-run), Gmail/recipient values are
    optional and default to empty strings so the API key alone suffices.

    When `require_supabase` is True (the web refresh job), the Supabase URL and
    service key are mandatory; otherwise they are optional and default to empty.
    """
    email_getter = _require if require_email else (lambda n: os.environ.get(n, ""))
    supabase_getter = _require if require_supabase else (lambda n: os.environ.get(n, ""))
    return Secrets(
        kicksdb_api_key=_require("KICKSDB_API_KEY"),
        gmail_address=email_getter("GMAIL_ADDRESS"),
        gmail_app_password=email_getter("GMAIL_APP_PASSWORD"),
        recipient_email=email_getter("RECIPIENT_EMAIL"),
        supabase_url=supabase_getter("SUPABASE_URL"),
        supabase_service_key=supabase_getter("SUPABASE_SERVICE_KEY"),
    )
