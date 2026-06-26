"""Web-platform refresh job: fetch releases, find all profitable upcoming ones,
and write the snapshot to Supabase.

This is a SEPARATE entrypoint from the weekly newsletter (`main.py`), which is left
untouched. The website reads the Supabase `releases` table for its list view; the
detail page fetches a single shoe live, so this snapshot only needs to be a daily
index of what's currently profitable.

Usage:
    python -m sneaker_aggregator.refresh             # fetch + upsert to Supabase
    python -m sneaker_aggregator.refresh --dry-run   # fetch + print row count, no write
"""

from __future__ import annotations

import argparse
import sys

from .analysis import find_opportunities
from .config import Config, load_config, load_secrets
from .sources.kicksdb import KicksDBClient
from .supabase_sink import prune_past, upsert_releases


def _web_profile(config: Config) -> Config:
    """Widen the email-shortlist config to 'every positive-profit upcoming release'.

    The list view wants the full set, not the curated top-N. We keep brands, fees,
    window and market from config.yaml, but drop the profit/margin gating (any profit
    above ~0 qualifies) and the result cap.
    """
    config.thresholds.min_profit = 0.01  # strictly positive net profit
    config.thresholds.min_margin = 0.0
    config.max_results = 0  # no cap
    return config


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Refresh the web platform's Supabase snapshot")
    p.add_argument("--dry-run", action="store_true", help="fetch + print row count, no write")
    p.add_argument("--config", default="config.yaml", help="path to config.yaml")
    p.add_argument("--no-prune", action="store_true", help="skip deleting past-dated rows")
    return p.parse_args(argv)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

    args = _parse_args(argv)
    config = _web_profile(load_config(args.config))
    secrets = load_secrets(require_email=False, require_supabase=not args.dry_run)

    with KicksDBClient(
        api_key=secrets.kicksdb_api_key,
        base_url=config.api.base_url,
        timeout=config.api.request_timeout_seconds,
        market=config.api.market,
    ) as client:
        releases = client.get_releases(
            config.brands,
            page_limit=config.api.page_limit,
            max_pages=config.api.max_pages,
        )

    print(f"Fetched {len(releases)} releases for {', '.join(config.brands)}")
    opportunities = find_opportunities(releases, config)
    print(f"Found {len(opportunities)} profitable upcoming releases")

    if args.dry_run:
        print(f"Dry run — would upsert {len(opportunities)} rows to Supabase")
        return 0

    written = upsert_releases(opportunities, config, secrets)
    print(f"Upserted {written} rows to Supabase")
    if not args.no_prune:
        prune_past(config, secrets)
        print("Pruned past-dated rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
