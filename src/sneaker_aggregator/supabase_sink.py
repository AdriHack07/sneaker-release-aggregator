"""Supabase sink for the web platform.

Writes the current snapshot of profitable upcoming releases to a Supabase Postgres
table (`releases`) via the PostgREST API, using the service-role key. The website
reads this table (public, read-only) for its list view.

No new dependency: we reuse `httpx` (already required by the KicksDB client).
The table schema lives in `supabase/schema.sql`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List

import httpx

from .config import Config, Secrets
from .models import Opportunity

# PostgREST batch-upsert tuning.
_TABLE = "releases"
_CHUNK = 200  # rows per request


def _row(opp: Opportunity, market: str, now_iso: str) -> Dict[str, Any]:
    """Flatten an Opportunity (+ its Release and MarketStats) into a table row."""
    r = opp.release
    s = r.stats
    return {
        # Core (always shown on the list)
        "sku": r.sku,
        "name": r.name,
        "brand": r.brand,
        "retail_price": r.retail_price,
        "release_date": r.release_date.isoformat() if r.release_date else None,
        "image_url": r.image_url,
        "stockx_url": r.stockx_url,
        "lowest_ask": r.lowest_ask,
        "profit": opp.profit,
        "margin": opp.margin,
        "net_payout": opp.net_payout,
        "resale_price": opp.resale_price,
        # Market depth (detail page)
        "avg_price": r.avg_price,
        "highest_ask": r.highest_ask,
        "sales_count": r.sales_count,
        "weekly_orders": r.weekly_orders,
        "annual_high": s.annual_high if s else None,
        "annual_low": s.annual_low if s else None,
        "annual_average_price": s.annual_average_price if s else None,
        "annual_sales_count": s.annual_sales_count if s else None,
        "annual_volatility": s.annual_volatility if s else None,
        "annual_price_premium": s.annual_price_premium if s else None,
        "annual_total_dollars": s.annual_total_dollars if s else None,
        "last_90_days_sales_count": s.last_90_days_sales_count if s else None,
        "last_90_days_average_price": s.last_90_days_average_price if s else None,
        "last_90_days_range_high": s.last_90_days_range_high if s else None,
        "last_90_days_range_low": s.last_90_days_range_low if s else None,
        "market": market,
        "updated_at": now_iso,
    }


def _headers(secrets: Secrets, extra: Dict[str, str] | None = None) -> Dict[str, str]:
    headers = {
        "apikey": secrets.supabase_service_key,
        "Authorization": f"Bearer {secrets.supabase_service_key}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def upsert_releases(
    opportunities: List[Opportunity], config: Config, secrets: Secrets
) -> int:
    """Upsert all opportunities into the `releases` table (on conflict: sku).

    Returns the number of rows written.
    """
    if not secrets.supabase_url or not secrets.supabase_service_key:
        raise RuntimeError("Supabase URL and service key are required to upsert.")

    now_iso = datetime.now(timezone.utc).isoformat()
    rows = [_row(opp, config.api.market, now_iso) for opp in opportunities]
    base = secrets.supabase_url.rstrip("/")
    url = f"{base}/rest/v1/{_TABLE}"

    with httpx.Client(timeout=config.api.request_timeout_seconds) as client:
        for start in range(0, len(rows), _CHUNK):
            chunk = rows[start : start + _CHUNK]
            resp = client.post(
                url,
                params={"on_conflict": "sku"},
                headers=_headers(
                    secrets,
                    {"Prefer": "resolution=merge-duplicates,return=minimal"},
                ),
                json=chunk,
            )
            resp.raise_for_status()
    return len(rows)


def prune_past(config: Config, secrets: Secrets, today: date | None = None) -> None:
    """Delete rows whose release_date is in the past, keeping the table = upcoming window.

    Undated (NULL release_date) rows are kept.
    """
    if not secrets.supabase_url or not secrets.supabase_service_key:
        raise RuntimeError("Supabase URL and service key are required to prune.")

    today = today or date.today()
    base = secrets.supabase_url.rstrip("/")
    url = f"{base}/rest/v1/{_TABLE}"
    with httpx.Client(timeout=config.api.request_timeout_seconds) as client:
        resp = client.delete(
            url,
            params={"release_date": f"lt.{today.isoformat()}"},
            headers=_headers(secrets, {"Prefer": "return=minimal"}),
        )
        resp.raise_for_status()
