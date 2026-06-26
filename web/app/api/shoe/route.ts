import { NextRequest, NextResponse } from "next/server";
import { Release } from "@/lib/types";

// Live single-shoe KicksDB lookup. Mirrors the parsing in
// src/sneaker_aggregator/sources/kicksdb.py so the detail page shows numbers that
// are current at view time (the daily Supabase snapshot can be hours old).
//
// The KicksDB key is server-only (KICKSDB_API_KEY, never NEXT_PUBLIC_*), so this
// must run server-side. Always dynamic — never cache a live price.
export const dynamic = "force-dynamic";

const BASE = "https://api.kicks.dev/v3";

function asFloat(v: unknown): number | null {
  if (v === null || v === undefined || v === "" || v === 0 || v === "0") return null;
  const f = typeof v === "number" ? v : parseFloat(String(v));
  return Number.isFinite(f) && f > 0 ? f : null;
}

function asInt(v: unknown): number | null {
  const f = asFloat(v);
  return f === null ? null : Math.trunc(f);
}

function asDate(v: unknown): string | null {
  if (!v) return null;
  const s = String(v).trim();
  const d = new Date(s);
  if (!Number.isNaN(d.getTime())) return d.toISOString().slice(0, 10);
  return null;
}

function traits(record: any): Record<string, string> {
  const out: Record<string, string> = {};
  for (const t of record?.traits ?? []) {
    if (t?.trait != null) out[t.trait] = t.value;
  }
  return out;
}

function parseProduct(record: any, market: string): Release | null {
  const name = record?.title ?? record?.name;
  if (!name) return null;
  const tr = traits(record);
  const sku = tr["Style"] ?? record?.sku;
  if (!sku) return null;
  const slug = record?.slug;
  const s = record?.statistics ?? {};

  return {
    sku: String(sku),
    name: String(name),
    brand: record?.brand ? String(record.brand) : null,
    retail_price: asFloat(tr["Retail Price"]),
    release_date: asDate(tr["Release Date"]),
    image_url: record?.image ?? null,
    stockx_url: slug ? `https://stockx.com/${slug}` : null,
    lowest_ask: asFloat(record?.min_price),
    avg_price: asFloat(record?.avg_price),
    highest_ask: asFloat(record?.max_price),
    sales_count: asInt(s.last_90_days_sales_count) ?? asInt(s.annual_sales_count),
    weekly_orders: asInt(record?.weekly_orders) ?? 0,
    annual_high: asFloat(s.annual_high),
    annual_low: asFloat(s.annual_low),
    annual_average_price: asFloat(s.annual_average_price),
    annual_sales_count: asInt(s.annual_sales_count),
    annual_volatility: asFloat(s.annual_volatility),
    annual_price_premium: asFloat(s.annual_price_premium),
    annual_total_dollars: asFloat(s.annual_total_dollars),
    last_90_days_sales_count: asInt(s.last_90_days_sales_count),
    last_90_days_average_price: asFloat(s.last_90_days_average_price),
    last_90_days_range_high: asFloat(s.last_90_days_range_high),
    last_90_days_range_low: asFloat(s.last_90_days_range_low),
    // Computed fields aren't returned live (the list/snapshot has them); leave null.
    profit: null,
    margin: null,
    net_payout: null,
    resale_price: null,
    market,
    updated_at: new Date().toISOString(),
  };
}

export async function GET(req: NextRequest) {
  const sku = req.nextUrl.searchParams.get("sku");
  if (!sku) {
    return NextResponse.json({ error: "missing sku" }, { status: 400 });
  }
  const apiKey = process.env.KICKSDB_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: "server not configured" }, { status: 500 });
  }
  const market = process.env.KICKSDB_MARKET || "US";

  // Query by exact style code. KicksDB's filter is SQL-ish; the Style trait is the
  // canonical SKU. Fall back to a free-text query if the filtered lookup misses.
  const params = new URLSearchParams({
    "filters": `style = '${sku.replace(/'/g, "")}'`,
    "display[traits]": "true",
    "display[statistics]": "true",
    market,
    limit: "5",
  });

  try {
    let resp = await fetch(`${BASE}/stockx/products?${params.toString()}`, {
      headers: { Authorization: apiKey },
      cache: "no-store",
    });
    let payload = resp.ok ? await resp.json() : null;
    let batch: any[] = (payload?.data ?? payload) || [];

    if (!Array.isArray(batch) || batch.length === 0) {
      // Fallback: free-text search on the SKU.
      const q = new URLSearchParams({
        query: sku,
        "display[traits]": "true",
        "display[statistics]": "true",
        market,
        limit: "5",
      });
      resp = await fetch(`${BASE}/stockx/products?${q.toString()}`, {
        headers: { Authorization: apiKey },
        cache: "no-store",
      });
      payload = resp.ok ? await resp.json() : null;
      batch = (payload?.data ?? payload) || [];
    }

    if (!Array.isArray(batch) || batch.length === 0) {
      return NextResponse.json({ error: "not found" }, { status: 404 });
    }

    // Prefer the record whose Style trait matches the requested SKU exactly.
    const want = sku.toUpperCase();
    const chosen =
      batch.find((rec) => {
        const tr = traits(rec);
        return String(tr["Style"] ?? rec?.sku ?? "").toUpperCase() === want;
      }) ?? batch[0];

    const release = parseProduct(chosen, market);
    if (!release) {
      return NextResponse.json({ error: "unparseable" }, { status: 502 });
    }
    return NextResponse.json({ release });
  } catch (e) {
    return NextResponse.json(
      { error: "kicksdb fetch failed" },
      { status: 502 }
    );
  }
}
