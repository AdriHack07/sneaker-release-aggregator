"""Render opportunities into HTML (Jinja2) and a plain-text fallback."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import Config
from .models import Opportunity

_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"

# Rough currency symbol per KicksDB market (USD-priced markets default to $).
_CURRENCY = {"US": "$", "UK": "£", "DE": "€", "FR": "€", "NL": "€", "IT": "€",
             "BE": "€", "FI": "€", "EU": "€", "CH": "CHF ", "DK": "kr ", "PL": "zł "}


def currency_symbol(market: str) -> str:
    return _CURRENCY.get(market.split(".")[0], "$")


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def subject_line(opportunities: List[Opportunity]) -> str:
    count = len(opportunities)
    if count == 0:
        return "👟 Weekly Sneaker Report — no opportunities this week"
    top = opportunities[0]
    return (
        f"👟 {count} sneaker flip opportunit{'y' if count == 1 else 'ies'} "
        f"— top +{top.profit:.0f} ({top.release.name})"
    )


def render_html(opportunities: List[Opportunity], config: Config) -> str:
    template = _env().get_template("report.html.j2")
    return template.render(
        opportunities=opportunities,
        total_count=len(opportunities),
        brands=config.brands,
        resale_signal=config.resale_signal,
        sort_by=config.sort_by,
        fee_pct=config.fees.total_pct,
        shipping_cost=config.fees.shipping_cost,
        market=config.api.market,
        cur=currency_symbol(config.api.market),
        generated_at=datetime.now().strftime("%A, %d %B %Y"),
    )


def render_text(opportunities: List[Opportunity], config: Config) -> str:
    if not opportunities:
        return "No releases cleared the profit thresholds this week."
    cur = currency_symbol(config.api.market)
    lines = [f"Weekly Sneaker Flip Report — {len(opportunities)} opportunities", ""]
    _text_section(lines, opportunities, cur)
    return "\n".join(lines)


def _text_section(lines: List[str], opportunities: List[Opportunity], cur: str) -> None:
    for o in opportunities:
        r = o.release
        s = r.stats
        drop = f" (drops {r.release_date})" if r.release_date else ""
        lines.append(f"{r.name} [{r.sku}]{drop}")
        lines.append(
            f"  Retail {cur}{r.retail_price:.0f} -> resale {cur}{o.resale_price:.0f} "
            f"-> net {cur}{o.net_payout:.0f} | PROFIT +{cur}{o.profit:.0f} ({o.margin * 100:.0f}%)"
        )
        asks = f"  Asks: low {cur}{r.lowest_ask:.0f}" if r.lowest_ask else "  Asks: —"
        if r.avg_price:
            asks += f" / avg {cur}{r.avg_price:.0f}"
        if r.highest_ask:
            asks += f" / high {cur}{r.highest_ask:.0f}"
        lines.append(asks)
        if s:
            parts = []
            if s.last_90_days_sales_count:
                parts.append(f"90d sales {s.last_90_days_sales_count}")
            if s.annual_sales_count:
                parts.append(f"annual sales {s.annual_sales_count}")
            if s.annual_volatility is not None:
                parts.append(f"volatility {s.annual_volatility * 100:.0f}%")
            if s.annual_price_premium is not None:
                parts.append(f"premium {s.annual_price_premium:.2f}x")
            if parts:
                lines.append("  " + " | ".join(parts))
        if r.stockx_url:
            lines.append(f"  Resale (StockX): {r.stockx_url}")
        lines.append("")
