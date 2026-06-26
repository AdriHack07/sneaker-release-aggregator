import Link from "next/link";
import { notFound } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { Release } from "@/lib/types";
import { money, percent, formatDate, daysUntil } from "@/lib/format";
import LiveMarket from "./live-market";
import RaffleFinder from "./raffle-finder";

export const revalidate = 3600;

export default async function ShoePage({
  params,
}: {
  params: { sku: string };
}) {
  const sku = decodeURIComponent(params.sku);
  const { data } = await supabase
    .from("releases")
    .select("*")
    .eq("sku", sku)
    .maybeSingle();

  if (!data) notFound();
  const r = data as Release;

  return (
    <main className="container">
      <div className="crumbs">
        <Link href="/">← Back to list</Link>
      </div>

      <div className="detail-head">
        <div className="detail-img">
          {r.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={r.image_url} alt={r.name} />
          ) : null}
        </div>
        <div className="detail-info">
          <h2>{r.name}</h2>
          <div className="muted" style={{ marginBottom: 12 }}>
            {r.brand} · {r.sku}
          </div>
          <span className="profit-badge" style={{ fontSize: 18 }}>
            +{money(r.profit, r.market)}
            <span style={{ opacity: 0.7, fontWeight: 500 }}>
              {percent(r.margin)} margin
            </span>
          </span>

          <div className="stat-grid" style={{ marginTop: 16 }}>
            <div className="stat">
              <div className="k">Release date</div>
              <div className="v">{formatDate(r.release_date)}</div>
              <div className="muted" style={{ fontSize: 12 }}>
                {daysUntil(r.release_date)}
              </div>
            </div>
            <div className="stat">
              <div className="k">Lowest ask</div>
              <div className="v">{money(r.lowest_ask, r.market)}</div>
            </div>
            <div className="stat">
              <div className="k">Sticker (retail)</div>
              <div className="v">{money(r.retail_price, r.market)}</div>
            </div>
            <div className="stat">
              <div className="k">Net payout</div>
              <div className="v">{money(r.net_payout, r.market)}</div>
            </div>
          </div>

          {r.stockx_url ? (
            <p style={{ marginTop: 16 }}>
              <a
                className="btn-ghost"
                href={r.stockx_url}
                target="_blank"
                rel="noreferrer"
              >
                View on StockX ↗
              </a>
            </p>
          ) : null}
        </div>
      </div>

      {/* Deep market data, fetched live at view time (falls back to snapshot). */}
      <LiveMarket sku={r.sku} snapshot={r} />

      {/* On-demand, never-stored list of raffle/retailer sites. */}
      <RaffleFinder sku={r.sku} name={r.name} />
    </main>
  );
}
