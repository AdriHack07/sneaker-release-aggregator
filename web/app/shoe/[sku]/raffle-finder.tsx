"use client";

import { useState } from "react";
import { Stockist } from "@/lib/types";
import { money } from "@/lib/format";

type State =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "done"; stockists: Stockist[] }
  | { phase: "error"; message: string };

export default function RaffleFinder({
  sku,
  name,
}: {
  sku: string;
  name: string;
}) {
  const [state, setState] = useState<State>({ phase: "idle" });

  async function find() {
    setState({ phase: "loading" });
    try {
      const params = new URLSearchParams({ sku, name });
      const res = await fetch(`/api/raffles?${params.toString()}`, {
        cache: "no-store",
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "lookup failed");
      setState({ phase: "done", stockists: json.stockists ?? [] });
    } catch (e: any) {
      setState({ phase: "error", message: e?.message || "lookup failed" });
    }
  }

  return (
    <div className="panel">
      <h3>Raffles &amp; retailers</h3>
      <p className="muted" style={{ marginTop: -4, marginBottom: 12 }}>
        Live lookup — fetched fresh each time and never stored, because raffle
        listings change in the days before a drop. The full list across regions
        (your alternatives to SNKRS).
      </p>

      {state.phase === "idle" || state.phase === "error" ? (
        <button className="btn" onClick={find}>
          Find raffle sites
        </button>
      ) : null}
      {state.phase === "loading" ? (
        <button className="btn" disabled>
          Searching live…
        </button>
      ) : null}

      {state.phase === "error" ? (
        <p className="live-note">
          Couldn&apos;t load right now ({state.message}). Try again.
        </p>
      ) : null}

      {state.phase === "done" && state.stockists.length === 0 ? (
        <p className="empty">
          No raffle/retailer listings found for this shoe yet. Check again closer
          to the release date.
        </p>
      ) : null}

      {state.phase === "done" && state.stockists.length > 0 ? (
        <div style={{ marginTop: 14 }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
            {state.stockists.length} sites · raffles first
          </div>
          {state.stockists.map((s, i) => (
            <a
              key={`${s.shop_name}-${i}`}
              className="stockist"
              href={s.url}
              target="_blank"
              rel="noreferrer"
            >
              <span>
                <span className={"tag " + (s.is_raffle ? "raffle" : "shop")}>
                  {s.is_raffle ? "RAFFLE" : "SHOP"}
                </span>{" "}
                {s.shop_name}
              </span>
              <span className="muted">
                {s.price != null ? money(s.price, "EU") : ""} ↗
              </span>
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}
