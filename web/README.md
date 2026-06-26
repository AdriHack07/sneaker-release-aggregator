# Sneaker Flip Radar — Web Platform

Public website (Next.js, App Router) on top of the existing Python aggregator.

- **List** (`/`): the full set of profitable upcoming releases (next 60 days), read
  from a daily Supabase snapshot. Sort by **profit** or **release date**.
- **Detail** (`/shoe/[sku]`): core info plus deep market data (volume, volatility,
  asks, sales history). Market figures are fetched **live** at view time from
  KicksDB (`/api/shoe`). Bids and the per-size ask ladder are labelled **N/A** —
  the data source exposes ask-side data only.
- **Raffles**: a **live, never-stored** lookup (`/api/raffles`) of every webstore
  listing the shoe for raffle/sale across regions (alternatives to SNKRS). Fetched
  fresh on each click because listings change in the days before a drop.

## How data flows

```
Python refresh job (../src/sneaker_aggregator/refresh.py)
  └─ daily GitHub Action ─► Supabase `releases` table ─► list & detail (snapshot)
                                                         ─► /api/shoe refreshes one shoe live
                                                         ─► /api/raffles lives Sneakerjagers
```

The weekly email newsletter (`../src/sneaker_aggregator/main.py`) is unchanged and
independent of this site.

## Local development

1. Create the Supabase table once: run `../supabase/schema.sql` in the Supabase SQL editor.
2. Populate it: from the repo root, `python -m sneaker_aggregator.refresh`
   (needs `KICKSDB_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).
3. `cp .env.local.example .env.local` and fill in the values.
4. `npm install && npm run dev`, then open http://localhost:3000.

## Environment variables

| Var | Where | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | public | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | public | anon key (RLS = read-only) |
| `KICKSDB_API_KEY` | **server only** | live single-shoe lookups in `/api/shoe` |
| `KICKSDB_MARKET` | server (optional) | pricing market, default `US` |

## Deploy (Vercel)

1. Import the GitHub repo into Vercel.
2. Set **Root Directory** = `web`.
3. Add the four env vars above in Project Settings → Environment Variables.
4. Deploy. Pushes to the repo auto-deploy.
