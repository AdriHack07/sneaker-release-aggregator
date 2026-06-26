"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Release, SortKey } from "@/lib/types";
import { money, percent, formatDate, daysUntil } from "@/lib/format";

function sortReleases(releases: Release[], sort: SortKey): Release[] {
  const copy = [...releases];
  if (sort === "date") {
    // Soonest first; undated (TBA) sort last; ties broken by higher profit.
    const FAR = "9999-12-31";
    copy.sort((a, b) => {
      const da = a.release_date ?? FAR;
      const db = b.release_date ?? FAR;
      if (da !== db) return da < db ? -1 : 1;
      return (b.profit ?? 0) - (a.profit ?? 0);
    });
  } else {
    copy.sort((a, b) => (b.profit ?? 0) - (a.profit ?? 0));
  }
  return copy;
}

export default function ReleaseList({ releases }: { releases: Release[] }) {
  const [sort, setSort] = useState<SortKey>("profit");
  const sorted = useMemo(() => sortReleases(releases, sort), [releases, sort]);

  return (
    <>
      <div className="toolbar">
        <span className="label">{releases.length} releases · sort by</span>
        <div className="seg">
          <button
            className={sort === "profit" ? "active" : ""}
            onClick={() => setSort("profit")}
          >
            Profit
          </button>
          <button
            className={sort === "date" ? "active" : ""}
            onClick={() => setSort("date")}
          >
            Release date
          </button>
        </div>
      </div>

      <div className="grid">
        {sorted.map((r) => (
          <Link key={r.sku} href={`/shoe/${encodeURIComponent(r.sku)}`}>
            <article className="card">
              <div className="imgwrap">
                {r.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={r.image_url} alt={r.name} loading="lazy" />
                ) : null}
              </div>
              <div className="body">
                <span className="profit-badge">
                  +{money(r.profit, r.market)}
                  <span style={{ opacity: 0.7, fontWeight: 500 }}>
                    {percent(r.margin)}
                  </span>
                </span>
                <div className="name">{r.name}</div>
                <div className="brand">{r.brand}</div>
                <div className="row">
                  <span className="k">Lowest ask</span>
                  <span>{money(r.lowest_ask, r.market)}</span>
                </div>
                <div className="row">
                  <span className="k">Retail</span>
                  <span>{money(r.retail_price, r.market)}</span>
                </div>
                <div className="meta">
                  <span>{formatDate(r.release_date)}</span>
                  <span>{daysUntil(r.release_date)}</span>
                </div>
              </div>
            </article>
          </Link>
        ))}
      </div>
    </>
  );
}
