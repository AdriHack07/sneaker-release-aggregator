"""Entrypoint: fetch releases, find opportunities, render and email the report.

Usage:
    python -m sneaker_aggregator.main              # fetch + email
    python -m sneaker_aggregator.main --dry-run    # write report.html, no email
    python -m sneaker_aggregator.main --dump       # print one raw product (debug fields)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis import find_opportunities
from .config import Config, load_config, load_secrets
from .email_sender import send_email
from .report import render_html, render_text, subject_line
from .sources.kicksdb import KicksDBClient
from .sources.sneakerjagers import SneakerjagersClient


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Sneaker release opportunity aggregator")
    p.add_argument("--dry-run", action="store_true", help="write report.html instead of emailing")
    p.add_argument("--dump", action="store_true", help="print one raw API product and exit")
    p.add_argument("--config", default="config.yaml", help="path to config.yaml")
    p.add_argument("--out", default="report.html", help="output path for --dry-run")
    p.add_argument("--sort", choices=["profit", "date"], help="override config sort order")
    return p.parse_args(argv)


def _enrich_stockists(opportunities, config: Config) -> None:
    """Annotate each opportunity with its raffle/retailer list from Sneakerjagers (free).

    Best-effort: any failure (bot block, missing match, site change) leaves an empty
    list, and the report falls back to per-shoe search links. Never raises.
    """
    if not opportunities:
        return
    try:
        with SneakerjagersClient(
            timeout=config.api.request_timeout_seconds,
            headless_fallback=config.stockists_headless_fallback,
        ) as sj:
            matched = 0
            for opp in opportunities:
                opp.release.stockists = sj.get_stockists_for_sku(
                    opp.release.sku, include_webshops=config.stockists_include_webshops
                )
                if opp.release.stockists:
                    matched += 1
            total = sum(len(o.release.stockists) for o in opportunities)
            print(f"Sneakerjagers: matched {matched}/{len(opportunities)} shoes, {total} retailer links")
    except Exception as e:  # noqa: BLE001 — enrichment must never break the report
        print(f"Sneakerjagers enrichment skipped ({e}) — using fallback links.")


def main(argv=None) -> int:
    # Emojis in log/subject output crash the default Windows console (cp1252).
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

    args = _parse_args(argv)
    config = load_config(args.config)
    if args.sort:
        config.sort_by = args.sort
    secrets = load_secrets(require_email=not (args.dry_run or args.dump))

    with KicksDBClient(
        api_key=secrets.kicksdb_api_key,
        base_url=config.api.base_url,
        timeout=config.api.request_timeout_seconds,
        market=config.api.market,
    ) as client:
        if args.dump:
            raw = client.fetch_raw_products(config.brands[0], page_limit=1, max_pages=1)
            print(json.dumps(raw[0] if raw else {}, indent=2, default=str))
            return 0

        releases = client.get_releases(
            config.brands,
            page_limit=config.api.page_limit,
            max_pages=config.api.max_pages,
        )

    print(f"Fetched {len(releases)} releases for {', '.join(config.brands)}")
    opportunities = find_opportunities(releases, config)
    print(f"Found {len(opportunities)} opportunities clearing thresholds")

    if config.fetch_stockists:
        _enrich_stockists(opportunities, config)

    html = render_html(opportunities, config)
    text = render_text(opportunities, config)
    subject = subject_line(opportunities)

    if args.dry_run:
        Path(args.out).write_text(html, encoding="utf-8")
        print(f"Dry run — wrote {args.out}")
        print(f"Subject would be: {subject}")
        return 0

    send_email(subject, html, text, secrets)
    print(f"Email sent to {secrets.recipient_email}: {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
