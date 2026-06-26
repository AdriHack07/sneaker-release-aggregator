// Mirrors the Supabase `releases` table (see supabase/schema.sql) and the live
// KicksDB detail shape. All market fields are nullable — brand-new releases have
// no trading history yet.

export interface Release {
  sku: string;
  name: string;
  brand: string | null;
  retail_price: number | null;
  release_date: string | null; // ISO date (YYYY-MM-DD)
  image_url: string | null;
  stockx_url: string | null;
  lowest_ask: number | null;
  profit: number | null;
  margin: number | null;
  net_payout: number | null;
  resale_price: number | null;

  // Market depth
  avg_price: number | null;
  highest_ask: number | null;
  sales_count: number | null;
  weekly_orders: number | null;
  annual_high: number | null;
  annual_low: number | null;
  annual_average_price: number | null;
  annual_sales_count: number | null;
  annual_volatility: number | null;
  annual_price_premium: number | null;
  annual_total_dollars: number | null;
  last_90_days_sales_count: number | null;
  last_90_days_average_price: number | null;
  last_90_days_range_high: number | null;
  last_90_days_range_low: number | null;

  market: string | null;
  updated_at: string | null;
}

export type SortKey = "profit" | "date";

// One retailer/raffle entry from the live Sneakerjagers lookup.
export interface Stockist {
  shop_name: string;
  url: string;
  price: number | null;
  is_raffle: boolean;
}
