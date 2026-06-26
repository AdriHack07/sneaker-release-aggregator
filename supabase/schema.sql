-- Supabase schema for the Sneaker Release Aggregator web platform.
-- Run this once in the Supabase SQL editor (or via the CLI) to create the
-- snapshot table the website reads and the daily refresh job writes.
--
-- The refresh job (src/sneaker_aggregator/refresh.py) writes with the
-- service-role key (bypasses RLS). The website reads with the anon key,
-- which is limited to SELECT by the policy below.

create table if not exists public.releases (
    -- Core (always shown on the list)
    sku                       text primary key,
    name                      text not null,
    brand                     text,
    retail_price              numeric,
    release_date              date,
    image_url                 text,
    stockx_url                text,
    lowest_ask                numeric,
    profit                    numeric,
    margin                    numeric,
    net_payout                numeric,
    resale_price              numeric,

    -- Market depth (detail page)
    avg_price                 numeric,
    highest_ask               numeric,
    sales_count               integer,
    weekly_orders             integer,
    annual_high               numeric,
    annual_low                numeric,
    annual_average_price      numeric,
    annual_sales_count        integer,
    annual_volatility         numeric,
    annual_price_premium      numeric,
    annual_total_dollars      numeric,
    last_90_days_sales_count  integer,
    last_90_days_average_price numeric,
    last_90_days_range_high   numeric,
    last_90_days_range_low    numeric,

    market                    text,
    updated_at                timestamptz default now()
);

-- Indexes for the two sort orders the list offers.
create index if not exists releases_profit_idx on public.releases (profit desc);
create index if not exists releases_release_date_idx on public.releases (release_date asc);

-- Row Level Security: public, read-only.
alter table public.releases enable row level security;

drop policy if exists "Public read access" on public.releases;
create policy "Public read access"
    on public.releases
    for select
    to anon
    using (true);
