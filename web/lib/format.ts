// Display helpers shared across pages.

const CURRENCY: Record<string, string> = {
  US: "$", UK: "£", DE: "€", FR: "€", NL: "€", IT: "€",
  BE: "€", FI: "€", EU: "€", CH: "CHF ", DK: "kr ", PL: "zł ",
};

export function currencySymbol(market: string | null | undefined): string {
  if (!market) return "$";
  return CURRENCY[market.split(".")[0]] ?? "$";
}

export function money(
  value: number | null | undefined,
  market?: string | null
): string {
  if (value === null || value === undefined) return "—";
  const sym = currencySymbol(market);
  return `${sym}${value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export function num(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString();
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "TBA";
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return "TBA";
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function daysUntil(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return "";
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((d.getTime() - today.getTime()) / 86_400_000);
  if (diff < 0) return "released";
  if (diff === 0) return "today";
  if (diff === 1) return "tomorrow";
  return `in ${diff} days`;
}
