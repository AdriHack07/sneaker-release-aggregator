"use client";

import { useEffect, useState } from "react";
import { Release } from "@/lib/types";
import { money, percent, num } from "@/lib/format";

function Stat({
  label,
  value,
  na,
}: {
  label: string;
  value: string;
  na?: boolean;
}) {
  return (
    <div className="stat">
      <div className="k">{label}</div>
      <div className={"v" + (na ? " na" : "")}>{value}</div>
    </div>
  );
}

export default function LiveMarket({
  sku,
  snapshot,
}: {
  sku: string;
  snapshot: Release;
}) {
  // Start from the snapshot so the section renders instantly, then refresh live.
  const [data, setData] = useState<Release>(snapshot);
  const [status, setStatus] = useState<"loading" | "live" | "snapshot">(
    "loading"
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/shoe?sku=${encodeURIComponent(sku)}`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error("not ok");
        const json = await res.json();
        if (!cancelled && json?.release) {
          // Keep the snapshot's computed economics (profit/margin/net) — the live
          // call only refreshes market figures.
          setData({ ...snapshot, ...json.release });
          setStatus("live");
        } else if (!cancelled) {
          setStatus("snapshot");
        }
      } catch {
        if (!cancelled) setStatus("snapshot");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku, snapshot]);

  const m = data.market;

  return (
    <>
      <div className="panel">
        <h3>
          Asks{" "}
          <span className="muted" style={{ textTransform: "none" }}>
            {status === "live"
              ? "· live"
              : status === "loading"
              ? "· refreshing…"
              : "· snapshot (live refresh failed)"}
          </span>
        </h3>
        <div className="stat-grid">
          <Stat label="Lowest ask" value={money(data.lowest_ask, m)} />
          <Stat label="Average ask" value={money(data.avg_price, m)} />
          <Stat label="Highest ask" value={money(data.highest_ask, m)} />
          <Stat label="Highest bid" value="N/A" na />
          <Stat label="Per-size ask ladder" value="N/A" na />
        </div>
        <p className="live-note">
          Bids and the per-size ask/bid ladder aren&apos;t exposed by the data
          source (StockX ask-side data only).
        </p>
      </div>

      <div className="panel">
        <h3>Volume &amp; volatility</h3>
        <div className="stat-grid">
          <Stat
            label="Annual $ volume"
            value={money(data.annual_total_dollars, m)}
          />
          <Stat
            label="Annual sales"
            value={num(data.annual_sales_count)}
          />
          <Stat
            label="Sales (90d)"
            value={num(data.last_90_days_sales_count)}
          />
          <Stat label="Weekly orders" value={num(data.weekly_orders)} />
          <Stat
            label="Volatility (annual)"
            value={percent(data.annual_volatility)}
          />
          <Stat
            label="Price premium"
            value={
              data.annual_price_premium != null
                ? `${data.annual_price_premium.toFixed(2)}×`
                : "—"
            }
          />
        </div>
      </div>

      <div className="panel">
        <h3>Sales history</h3>
        <div className="stat-grid">
          <Stat label="Annual high" value={money(data.annual_high, m)} />
          <Stat label="Annual low" value={money(data.annual_low, m)} />
          <Stat
            label="Annual average"
            value={money(data.annual_average_price, m)}
          />
          <Stat
            label="90d average"
            value={money(data.last_90_days_average_price, m)}
          />
          <Stat
            label="90d range high"
            value={money(data.last_90_days_range_high, m)}
          />
          <Stat
            label="90d range low"
            value={money(data.last_90_days_range_low, m)}
          />
        </div>
      </div>
    </>
  );
}
