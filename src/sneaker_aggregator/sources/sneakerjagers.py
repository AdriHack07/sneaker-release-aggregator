"""Sneakerjagers source — free, per-shoe raffle/retailer lists.

Sneakerjagers is a Next.js app whose internal data endpoints are reachable without a key:

* Homepage HTML embeds ``"buildId":"..."`` (rotates per deploy — fetched each run).
* Brand listing JSON:
  ``/_next/data/{buildId}/en/sneakers/search.json?brands=jordan``
  -> ``pageProps.data.items[]`` = {id, slug, name, release_date, ...}, newest first.
  The ``slug`` ends with the stylecode (e.g. ``...-im0701-001``) — our SKU join key.
* Per-shoe JSON:
  ``/_next/data/{buildId}/en/s/{slug}/{id}.json``
  -> ``pageProps.item`` with ``links_raffles[]`` / ``links_webshops[]``, each
  {id, shop, prices:{eur,usd,...}, release_date_formatted}.
* Outbound link per entry: ``https://sneakerjagers.com/en/go/{link_id}`` (302 -> retailer).

These are undocumented endpoints: requests use browser headers + retries, and a headless
browser (Playwright) is used as a fallback when plain HTTP is bot-blocked. Everything degrades
gracefully — callers treat an empty result as "no data" and fall back to search links.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..models import Stockist

BASE = "https://sneakerjagers.com"
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Stylecode at the end of a slug, e.g. "...-burgundy-crush-im0701-001" -> "IM0701-001".
_STYLECODE_RE = re.compile(r"([a-z]{1,3}[0-9]{3,5}-[0-9]{3})$")
_BUILD_ID_RE = re.compile(r'"buildId":"([^"]+)"')


def stylecode_from_slug(slug: str) -> Optional[str]:
    """Extract a normalised stylecode (SKU) from a Sneakerjagers slug, if present."""
    if not slug:
        return None
    m = _STYLECODE_RE.search(slug.strip().lower())
    return m.group(1).upper() if m else None


def _price_from(prices: Any) -> Optional[float]:
    """Pick a representative price (prefer EUR, then native) from a prices map."""
    if not isinstance(prices, dict):
        return None
    for key in ("eur", "native", "gbp", "usd"):
        v = prices.get(key)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return None


def parse_links(item: Dict[str, Any], include_webshops: bool = True) -> List[Stockist]:
    """Turn an item's raffle (and optionally webshop) links into deduped Stockists.

    Raffles are listed first; within each group, cheapest known price first.
    """
    groups: List[Tuple[List[Dict[str, Any]], bool]] = [
        (item.get("links_raffles") or [], True),
    ]
    if include_webshops:
        groups.append((item.get("links_webshops") or [], False))

    by_shop: Dict[str, Stockist] = {}
    for links, is_raffle in groups:
        for link in links:
            shop = link.get("shop")
            link_id = link.get("id")
            if not shop or not link_id:
                continue
            price = _price_from(link.get("prices"))
            url = f"{BASE}/en/go/{link_id}"
            existing = by_shop.get(shop)
            if existing is None or (
                price is not None and (existing.price is None or price < existing.price)
            ):
                by_shop[shop] = Stockist(
                    shop_name=shop, link=url, price=price, is_raffle=is_raffle
                )
    return sorted(
        by_shop.values(),
        key=lambda s: (s.price is None, s.price or 0, s.shop_name.lower()),
    )


class SneakerjagersClient:
    def __init__(self, timeout: int = 30, headless_fallback: bool = True, retries: int = 3):
        self.timeout = timeout
        self.headless_fallback = headless_fallback
        self.retries = retries
        self._build_id: Optional[str] = None
        self._headless_blocked = False  # once Playwright is known-unavailable, stop trying
        self._client = httpx.Client(
            base_url=BASE, headers=BROWSER_HEADERS, timeout=timeout, follow_redirects=True
        )

    def __enter__(self) -> "SneakerjagersClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- low-level fetch --------------------------------------------------------

    def _get_text(self, path: str) -> Optional[str]:
        for attempt in range(self.retries):
            try:
                r = self._client.get(path)
                if r.status_code == 200 and len(r.text) > 200:
                    return r.text
            except httpx.HTTPError:
                pass
            time.sleep(1 + attempt)
        return None

    def get_build_id(self) -> Optional[str]:
        if self._build_id:
            return self._build_id
        html = self._get_text("/en")
        if html:
            m = _BUILD_ID_RE.search(html)
            if m:
                self._build_id = m.group(1)
        return self._build_id

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch JSON via httpx, falling back to a headless browser if bot-blocked."""
        for attempt in range(self.retries):
            try:
                r = self._client.get(path, params=params)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 404:
                    return None
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(1 + attempt)
        if self.headless_fallback and not self._headless_blocked:
            return self._get_json_headless(path, params)
        return None

    def _get_json_headless(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch JSON from within a real browser context (bypasses most bot checks)."""
        try:
            from playwright.sync_api import sync_playwright  # lazy: optional dependency
        except ImportError:
            self._headless_blocked = True
            print("  (headless fallback unavailable: playwright not installed)")
            return None
        url = str(httpx.URL(BASE + path, params=params or {}))
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=BROWSER_HEADERS["User-Agent"])
                page.goto(BASE + "/en", wait_until="domcontentloaded", timeout=self.timeout * 1000)
                data = page.evaluate(
                    "async (u) => { const r = await fetch(u); return r.ok ? await r.json() : null; }",
                    url,
                )
                browser.close()
                return data
        except Exception as e:  # noqa: BLE001 — headless is best-effort
            print(f"  (headless fallback failed: {e})")
            return None

    # -- high-level API ---------------------------------------------------------

    def _search(self, query: str) -> List[Dict[str, Any]]:
        """Run a search query and return its raw items (empty on failure)."""
        data = self._get_json("/api/sneakers/search", params={"query": query})
        return (data or {}).get("items") or []

    def _pick(self, items: List[Dict[str, Any]], want: str) -> Optional[Tuple[str, str]]:
        """Choose the item whose slug carries the wanted stylecode, else a confident
        single/few-hit match — never the unfiltered default. Returns (slug, id)."""
        if not items:
            return None
        coded = [it for it in items if stylecode_from_slug(it.get("slug") or "") == want]
        chosen = coded[0] if coded else (items[0] if len(items) <= 5 else None)
        if chosen and chosen.get("slug") and chosen.get("id"):
            return (chosen["slug"], str(chosen["id"]))
        return None

    def find_by_sku(self, sku: str) -> Optional[Tuple[str, str]]:
        """Find a shoe's (slug, id) by searching its SKU via /api/sneakers/search.

        A SKU query is precise (usually one hit). We accept a result when its slug
        carries the same stylecode, or when the search returned only a few hits
        (slug lacks a code but the SKU clearly matched) — never the unfiltered default.
        """
        return self._pick(self._search(sku), sku.upper())

    def find_by_name(self, name: str, sku: str = "") -> Optional[Tuple[str, str]]:
        """Fallback lookup by shoe name when the SKU isn't indexed under that code.

        Prefer a hit whose slug stylecode matches the SKU; otherwise accept a
        confident single/few-hit name match.
        """
        if not name:
            return None
        return self._pick(self._search(name), sku.upper())

    def get_raffles(self, slug: str, sid: str, include_webshops: bool = True) -> List[Stockist]:
        """Fetch the per-shoe page and return its raffle/webshop retailers."""
        build_id = self.get_build_id()
        if not build_id:
            return []
        data = self._get_json(f"/_next/data/{build_id}/en/s/{slug}/{sid}.json")
        item = ((data or {}).get("pageProps") or {}).get("item") or {}
        return parse_links(item, include_webshops=include_webshops)

    def get_stockists_for_sku(
        self, sku: str, name: str = "", include_webshops: bool = True
    ) -> List[Stockist]:
        """Convenience: SKU (with optional name fallback) -> retailer list (empty if not found)."""
        match = self.find_by_sku(sku)
        if not match and name:
            match = self.find_by_name(name, sku)
        if not match:
            return []
        return self.get_raffles(match[0], match[1], include_webshops=include_webshops)
