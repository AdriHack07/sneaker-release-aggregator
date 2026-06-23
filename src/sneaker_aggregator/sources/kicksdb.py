"""KicksDB (kicks.dev) StockX API client.

Reverse-engineered against the live API (June 2026). Key facts:

* Auth header is the raw API key: ``Authorization: <key>`` (no "Bearer" prefix).
* Endpoint: ``GET {base_url}/stockx/products``
  - ``filters``           SQL-ish, e.g. ``brand = 'Jordan'``
  - ``sort``              ``release_date`` (newest/future first) or ``rank``
  - ``display[traits]``   adds the ``traits`` array (Retail Price, Release Date, Style)
  - ``display[statistics]`` adds the ``statistics`` object (sales counts)
  - ``market``            pricing market, e.g. ``US`` or ``DE``
  - ``page`` / ``limit``  pagination
* Resale price lives at the product level as ``min_price`` (lowest ask across sizes),
  with ``avg_price`` as an alternative. Upcoming releases that aren't trading yet
  report ``min_price == 0``.
* Retail price and release date are ONLY in ``traits`` (a list of {trait, value}).

Use ``main.py --dump`` to print a raw product if the API shape changes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

import httpx

from ..models import MarketStats, Release


def _as_float(val: Any) -> Optional[float]:
    if val in (None, "", 0, "0"):
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _as_int(val: Any) -> Optional[int]:
    f = _as_float(val)
    return int(f) if f is not None else None


def _as_date(val: Any) -> Optional[date]:
    if not val:
        return None
    s = str(val).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _traits(record: Dict[str, Any]) -> Dict[str, str]:
    """Flatten the traits list ([{trait, value}, ...]) into a dict."""
    out: Dict[str, str] = {}
    for t in record.get("traits") or []:
        name = t.get("trait")
        if name is not None:
            out[name] = t.get("value")
    return out


def parse_product(record: Dict[str, Any]) -> Optional[Release]:
    """Convert a raw KicksDB StockX product into a Release, or None if unusable."""
    name = record.get("title") or record.get("name")
    if not name:
        return None

    traits = _traits(record)
    # Prefer the "Style" trait (true style id) over the noisy top-level sku field.
    sku = traits.get("Style") or record.get("sku")
    if not sku:
        return None

    slug = record.get("slug")
    raw_stats = record.get("statistics") or {}
    stats = MarketStats(
        annual_high=_as_float(raw_stats.get("annual_high")),
        annual_low=_as_float(raw_stats.get("annual_low")),
        annual_average_price=_as_float(raw_stats.get("annual_average_price")),
        annual_sales_count=_as_int(raw_stats.get("annual_sales_count")),
        annual_volatility=_as_float(raw_stats.get("annual_volatility")),
        annual_price_premium=_as_float(raw_stats.get("annual_price_premium")),
        annual_total_dollars=_as_float(raw_stats.get("annual_total_dollars")),
        last_90_days_sales_count=_as_int(raw_stats.get("last_90_days_sales_count")),
        last_90_days_average_price=_as_float(raw_stats.get("last_90_days_average_price")),
        last_90_days_range_high=_as_float(raw_stats.get("last_90_days_range_high")),
        last_90_days_range_low=_as_float(raw_stats.get("last_90_days_range_low")),
    )

    return Release(
        sku=str(sku),
        name=str(name),
        brand=str(record.get("brand") or "Unknown"),
        retail_price=_as_float(traits.get("Retail Price")),
        release_date=_as_date(traits.get("Release Date")),
        image_url=record.get("image"),
        stockx_url=f"https://stockx.com/{slug}" if slug else None,
        lowest_ask=_as_float(record.get("min_price")),
        avg_price=_as_float(record.get("avg_price")),
        highest_ask=_as_float(record.get("max_price")),
        sales_count=(
            stats.last_90_days_sales_count or stats.annual_sales_count
        ),
        weekly_orders=_as_int(record.get("weekly_orders")) or 0,
        stats=stats,
    )


class KicksDBClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.kicks.dev/v3",
        timeout: int = 30,
        market: str = "US",
    ):
        self.market = market
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": api_key},  # raw key, no "Bearer"
            timeout=timeout,
        )

    def __enter__(self) -> "KicksDBClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def fetch_raw_products(
        self, brand: str, page_limit: int = 50, max_pages: int = 4
    ) -> List[Dict[str, Any]]:
        """Page through StockX products for a brand, newest releases first."""
        results: List[Dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            resp = self._client.get(
                "/stockx/products",
                params={
                    "filters": f"brand = '{brand}'",
                    "sort": "release_date",
                    "display[traits]": "true",
                    "display[statistics]": "true",
                    "market": self.market,
                    "limit": page_limit,
                    "page": page,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            batch = payload.get("data") if isinstance(payload, dict) else payload
            if not batch:
                break
            results.extend(batch)
            if len(batch) < page_limit:
                break
        return results

    def get_releases(
        self, brands: Iterable[str], page_limit: int = 50, max_pages: int = 4
    ) -> List[Release]:
        """Fetch releases for the given brands, de-duplicated by SKU."""
        by_sku: Dict[str, Release] = {}
        for brand in brands:
            for record in self.fetch_raw_products(brand, page_limit, max_pages):
                release = parse_product(record)
                if release and release.sku not in by_sku:
                    by_sku[release.sku] = release
        return list(by_sku.values())
