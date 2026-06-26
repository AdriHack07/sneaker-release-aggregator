import { NextRequest, NextResponse } from "next/server";
import { Stockist } from "@/lib/types";

// Live raffle/retailer lookup via Sneakerjagers' internal (unauthenticated) Next.js
// data endpoints. Ported from src/sneaker_aggregator/sources/sneakerjagers.py
// (git commit bd81c33). Always fetched fresh and never stored — raffle listings
// change drastically in the days before a drop.
//
// Flow:
//   1. GET /en, extract "buildId" from the HTML.
//   2. Search by SKU (then name) via /api/sneakers/search?query=...
//   3. GET /_next/data/{buildId}/en/s/{slug}/{id}.json -> links_raffles[] + links_webshops[]
export const dynamic = "force-dynamic";

const BASE = "https://sneakerjagers.com";
const HEADERS: Record<string, string> = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
  Accept: "text/html,application/json;q=0.9,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9",
};

const STYLECODE_RE = /([a-z]{1,3}[0-9]{3,5}-[0-9]{3})$/;
const BUILD_ID_RE = /"buildId":"([^"]+)"/;

function stylecodeFromSlug(slug: string): string | null {
  if (!slug) return null;
  const m = STYLECODE_RE.exec(slug.trim().toLowerCase());
  return m ? m[1].toUpperCase() : null;
}

function priceFrom(prices: any): number | null {
  if (!prices || typeof prices !== "object") return null;
  for (const key of ["eur", "native", "gbp", "usd"]) {
    const v = prices[key];
    if (typeof v === "number" && v > 0) return v;
  }
  return null;
}

async function getText(path: string): Promise<string | null> {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const r = await fetch(BASE + path, { headers: HEADERS, cache: "no-store" });
      if (r.ok) {
        const text = await r.text();
        if (text.length > 200) return text;
      }
    } catch {
      /* retry */
    }
  }
  return null;
}

async function getJson(path: string): Promise<any | null> {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const r = await fetch(BASE + path, { headers: HEADERS, cache: "no-store" });
      if (r.status === 200) return await r.json();
      if (r.status === 404) return null;
    } catch {
      /* retry */
    }
  }
  return null;
}

let cachedBuildId: string | null = null;
async function getBuildId(): Promise<string | null> {
  if (cachedBuildId) return cachedBuildId;
  const html = await getText("/en");
  if (html) {
    const m = BUILD_ID_RE.exec(html);
    if (m) cachedBuildId = m[1];
  }
  return cachedBuildId;
}

async function search(query: string): Promise<any[]> {
  const data = await getJson(
    `/api/sneakers/search?query=${encodeURIComponent(query)}`
  );
  return (data?.items as any[]) ?? [];
}

// Pick the item whose slug carries the wanted stylecode, else a confident
// single/few-hit match — never the unfiltered default.
function pick(items: any[], want: string): [string, string] | null {
  if (!items.length) return null;
  const coded = items.filter(
    (it) => stylecodeFromSlug(it?.slug ?? "") === want
  );
  const chosen = coded[0] ?? (items.length <= 5 ? items[0] : null);
  if (chosen?.slug && chosen?.id) return [chosen.slug, String(chosen.id)];
  return null;
}

function parseLinks(item: any): Stockist[] {
  const groups: [any[], boolean][] = [
    [item?.links_raffles ?? [], true],
    [item?.links_webshops ?? [], false],
  ];
  const byShop = new Map<string, Stockist>();
  for (const [links, isRaffle] of groups) {
    for (const link of links) {
      const shop = link?.shop;
      const linkId = link?.id;
      if (!shop || !linkId) continue;
      const price = priceFrom(link?.prices);
      const url = `${BASE}/en/go/${linkId}`;
      const existing = byShop.get(shop);
      if (
        !existing ||
        (price != null && (existing.price == null || price < existing.price))
      ) {
        byShop.set(shop, { shop_name: shop, url, price, is_raffle: isRaffle });
      }
    }
  }
  // Raffles first, then by cheapest known price, then name.
  return [...byShop.values()].sort((a, b) => {
    if (a.is_raffle !== b.is_raffle) return a.is_raffle ? -1 : 1;
    const ap = a.price ?? Infinity;
    const bp = b.price ?? Infinity;
    if (ap !== bp) return ap - bp;
    return a.shop_name.toLowerCase().localeCompare(b.shop_name.toLowerCase());
  });
}

export async function GET(req: NextRequest) {
  const sku = req.nextUrl.searchParams.get("sku") || "";
  const name = req.nextUrl.searchParams.get("name") || "";
  if (!sku && !name) {
    return NextResponse.json({ error: "missing sku/name" }, { status: 400 });
  }

  try {
    const buildId = await getBuildId();
    if (!buildId) {
      return NextResponse.json(
        { error: "source unavailable" },
        { status: 502 }
      );
    }

    const want = sku.toUpperCase();
    let match = sku ? pick(await search(sku), want) : null;
    if (!match && name) match = pick(await search(name), want);
    if (!match) {
      return NextResponse.json({ stockists: [] });
    }

    const [slug, id] = match;
    const data = await getJson(`/_next/data/${buildId}/en/s/${slug}/${id}.json`);
    const item = data?.pageProps?.item ?? {};
    return NextResponse.json({ stockists: parseLinks(item) });
  } catch {
    return NextResponse.json({ error: "lookup failed" }, { status: 502 });
  }
}
