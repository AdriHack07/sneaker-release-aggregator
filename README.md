# 👟 Sneaker Release Opportunity Aggregator

Aggregates upcoming/recent **Nike + Jordan** sneaker releases, compares the **retail
buy price** against the **StockX resale price** (net of platform fees), and emails
a **weekly report** of profitable flip opportunities with detailed market data. Runs free
on **GitHub Actions** and sends via **Gmail SMTP**.

## How it works

1. Fetch releases for the configured brands from the [KicksDB](https://kicks.dev) StockX API
   (`/v3/stockx/products`, sorted by release date, with `display[traits]` + `display[statistics]`).
   One call per brand returns catalog data, retail price + release date (from *traits*), the
   resale asks (`min_price` / `avg_price` / `max_price`), and historical statistics.
2. For each release, compute **net payout** = resale × (1 − fees) − shipping, then
   **profit** = net payout − retail and **margin** = profit / retail.
3. Keep only releases that clear the profit / margin (and optional liquidity) thresholds;
   rank by profit.
4. Render an HTML email and send it via Gmail.

The profitability math lives in [`analysis.py`](src/sneaker_aggregator/analysis.py) and is
fully unit-tested.

## Data in each opportunity

Retail price · release date · lowest / average / highest ask · estimated net payout · profit
& margin · weekly orders · 90-day sales count & average · annual sales count, average,
range (low–high), volatility, resale premium, and total dollar volume.

**Where to buy / enter raffles:** each shoe is annotated with the full list of retailers
running a raffle for it (plus retail webshops), with direct links — sourced for free from
[Sneakerjagers](https://sneakerjagers.com). Shoes Sneakerjagers doesn't list (e.g. obscure
US-exclusive packs) fall back to a per-shoe Sole Retriever / Nike search link.

> **Note on bids:** KicksDB's StockX API exposes **ask-side data only** — there is no bid
> (highest offer) field, so bids are not in the report. Statistics are blank for brand-new
> releases that have not started trading yet.

> **Note on raffle data:** Sneakerjagers is accessed via its free, undocumented internal
> endpoints (no key). The lookup uses browser headers + retries and an optional headless
> browser (Playwright) fallback if a request is bot-blocked; if it ever changes, only the
> raffle annotations are affected — the rest of the report keeps working.

## Setup

### 1. Get the credentials

- **KicksDB API key** — sign up at <https://kicks.dev> (free tier ≈ 1,000 req/month, plenty
  for a weekly run). Paid tiers start at €29/mo if you need more.
- **Gmail App Password** — enable 2-Step Verification on your Google account, then create an
  App Password at <https://myaccount.google.com/apppasswords>. Use that 16-character value
  (not your normal password).

### 2. Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
pip install pytest                                   # for tests only

# Optional: headless-browser fallback for raffle lookups (recommended for CI):
pip install -e ".[headless]" && python -m playwright install chromium

cp .env.example .env        # then edit .env with your real values

# Inspect a raw API product (use this to confirm/extend field mappings):
python -m sneaker_aggregator.main --dump

# Generate report.html without sending an email:
python -m sneaker_aggregator.main --dry-run

# Actually send the email:
python -m sneaker_aggregator.main
```

Run the tests:

```bash
pytest
```

### 3. Deploy to GitHub Actions

1. Push this repo to GitHub.
2. In **Settings → Secrets and variables → Actions**, add four repository secrets:
   `KICKSDB_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `RECIPIENT_EMAIL`.
3. The [`weekly-report.yml`](.github/workflows/weekly-report.yml) workflow runs every Monday
   at 08:00 UTC. Trigger it manually first via **Actions → Weekly Sneaker Report → Run
   workflow** to confirm the email arrives.

## Configuration

All tunables live in [`config.yaml`](config.yaml) (secrets stay in env vars):

- `brands` — which brands to track (default Nike, Jordan). Must match StockX brand names.
- `window` — how far back/ahead (in days) to consider releases by release date.
- `fees` — commission %, payment processing %, and per-sale shipping cost.
- `thresholds` — `min_profit`, `min_margin`, and `min_sales_count` (liquidity guard; default
  `0` / off, because new & upcoming releases have no sales history yet).
- `resale_signal` — `lowest_ask` (default) or `average`.
- `sort_by` — `profit` (default) or `date` (soonest release first). Override per run with
  `--sort profit|date`.
- `raffle_sites` — quick-links shown in the report footer (used as a fallback when a shoe
  isn't matched on Sneakerjagers).
- `fetch_stockists` — annotate each shoe with its raffle/retailer list from Sneakerjagers
  (default true). `stockists_include_webshops` also lists plain retail webshops;
  `stockists_headless_fallback` enables the Playwright fallback when bot-blocked.
- `api.market` — pricing market (`US`, `DE`, `EU`, `UK`, …); set to your resale market.
- `max_results` — cap on opportunities per email.

## Notes & caveats

- **Estimates only.** Resale prices are volatile and fees vary by seller level — verify on
  StockX before buying.
- **Data quality.** The feed includes thin-market asks (one inflated listing with no sales
  behind it) and "Opened Packaging" / used-box listings; these can produce false positives
  at the top of the ranking. Judge each pick using the sales-count and volatility columns.
- **Field mapping.** Retail price and release date come from the StockX *traits* array;
  resale prices from `min_price`/`avg_price`/`max_price`. If the API shape changes, run
  `python -m sneaker_aggregator.main --dump` to inspect a raw product and adjust
  [`sources/kicksdb.py`](src/sneaker_aggregator/sources/kicksdb.py).
- **Market reality (2026).** Resale margins have compressed; tune `thresholds` so the report
  stays useful rather than empty or noisy.

## Project layout

```
src/sneaker_aggregator/
  config.py            # config.yaml + env secrets
  models.py            # Release, MarketStats, Opportunity
  sources/kicksdb.py        # KicksDB StockX API client (releases + market data)
  sources/sneakerjagers.py  # free per-shoe raffle/retailer lookup (+ headless fallback)
  analysis.py          # profit/margin/filter/rank  (unit-tested core)
  report.py            # Jinja2 HTML + text rendering
  email_sender.py      # Gmail SMTP
  main.py              # entrypoint (--dry-run, --dump)
templates/report.html.j2
tests/test_analysis.py
.github/workflows/weekly-report.yml
config.yaml
```
