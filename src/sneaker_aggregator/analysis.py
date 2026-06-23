"""Profit/margin computation, filtering and ranking — the testable core."""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

from .config import Config, Fees, Thresholds, Window
from .models import Opportunity, Release


def net_payout(resale_price: float, fees: Fees) -> float:
    """Take-home after platform commission, processing fees and shipping."""
    return resale_price * (1 - fees.total_pct) - fees.shipping_cost


def evaluate(release: Release, config: Config, today: Optional[date] = None) -> Optional[Opportunity]:
    """Compute the opportunity for a release, or None if it can't/shouldn't qualify.

    Returns None when required data is missing (retail or resale price) or when the
    release fails any threshold (profit, margin, liquidity).
    """
    retail = release.retail_price
    resale = release.resale_price(config.resale_signal)
    if not retail or retail <= 0 or not resale or resale <= 0:
        return None

    t: Thresholds = config.thresholds
    if t.min_sales_count > 0 and (release.sales_count or 0) < t.min_sales_count:
        return None

    payout = net_payout(resale, config.fees)
    profit = payout - retail
    margin = profit / retail

    if profit < t.min_profit or margin < t.min_margin:
        return None

    return Opportunity(
        release=release,
        resale_price=resale,
        net_payout=round(payout, 2),
        profit=round(profit, 2),
        margin=round(margin, 4),
    )


def in_window(release: Release, window: Window, today: date) -> bool:
    """True if the release date is within the configured window (or unknown)."""
    if release.release_date is None:
        return True  # keep undated products rather than silently dropping them
    start = today - timedelta(days=window.past_days)
    end = today + timedelta(days=window.future_days)
    return start <= release.release_date <= end


def _brand_match(release: Release, brands: List[str]) -> bool:
    rb = (release.brand or "").lower()
    return any(b.lower() in rb or rb in b.lower() for b in brands)


def find_opportunities(
    releases: List[Release], config: Config, today: Optional[date] = None
) -> List[Opportunity]:
    """Filter to brand + window, evaluate each, rank by profit desc, apply max_results."""
    today = today or date.today()
    opportunities: List[Opportunity] = []
    for release in releases:
        if not _brand_match(release, config.brands):
            continue
        if not in_window(release, config.window, today):
            continue
        opp = evaluate(release, config, today)
        if opp is not None:
            opportunities.append(opp)

    opportunities.sort(key=lambda o: o.profit, reverse=True)
    if config.max_results > 0:
        opportunities = opportunities[: config.max_results]
    return opportunities
