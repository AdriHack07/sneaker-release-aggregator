"""Core data models for releases, market data, and computed opportunities."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class MarketStats(BaseModel):
    """StockX historical market statistics (from KicksDB `display[statistics]`).

    All optional — brand-new / upcoming releases have no history yet (all zeros,
    which we normalise to None). Currency matches the configured market.
    """

    annual_high: Optional[float] = None
    annual_low: Optional[float] = None
    annual_average_price: Optional[float] = None
    annual_sales_count: Optional[int] = None
    annual_volatility: Optional[float] = None       # e.g. 0.15 = 15%
    annual_price_premium: Optional[float] = None    # resale / retail multiple
    annual_total_dollars: Optional[float] = None
    last_90_days_sales_count: Optional[int] = None
    last_90_days_average_price: Optional[float] = None
    last_90_days_range_high: Optional[float] = None
    last_90_days_range_low: Optional[float] = None


class Stockist(BaseModel):
    """A retailer/raffle where a shoe is (or will be) sold, with a direct link."""

    shop_name: str
    link: str
    price: Optional[float] = None  # listed price at that shop, if provided


class Release(BaseModel):
    """A sneaker release (buy side) plus its live resale market data (sell side).

    KicksDB returns both the catalog info and market figures on the same product
    record, so we keep them together. Any field may be missing for brand-new SKUs.
    """

    sku: str
    name: str
    brand: str
    retail_price: Optional[float] = None
    release_date: Optional[date] = None
    image_url: Optional[str] = None
    stockx_url: Optional[str] = None

    # Resale market signals (in the same currency as retail_price).
    # lowest_ask is StockX's product-level min_price (cheapest size in stock);
    # avg_price / highest_ask are across sizes. All 0/None until a shoe trades.
    lowest_ask: Optional[float] = None
    avg_price: Optional[float] = None
    highest_ask: Optional[float] = None
    sales_count: Optional[int] = None  # recent sales (90d/annual) — 0 for new releases
    weekly_orders: int = 0
    stats: Optional[MarketStats] = None

    # Retailers/raffles selling this shoe (populated from the unified endpoint; empty
    # on the free tier). Excludes resale marketplaces — these are where you BUY.
    stockists: List[Stockist] = Field(default_factory=list)

    def resale_price(self, prefer: str) -> Optional[float]:
        """Return the chosen resale signal, falling back to the other if missing.

        `prefer` is "lowest_ask" or "average".
        """
        primary = self.lowest_ask if prefer == "lowest_ask" else self.avg_price
        secondary = self.avg_price if prefer == "lowest_ask" else self.lowest_ask
        return primary if primary is not None else secondary


class Opportunity(BaseModel):
    """A release that clears the profitability thresholds, with computed economics."""

    release: Release
    resale_price: float       # the signal used for the calculation
    net_payout: float         # resale minus fees and shipping
    profit: float             # net_payout minus retail
    margin: float             # profit / retail
