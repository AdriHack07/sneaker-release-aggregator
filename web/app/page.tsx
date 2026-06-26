import { supabase } from "@/lib/supabase";
import { Release } from "@/lib/types";
import ReleaseList from "./release-list";

// The list is a daily snapshot — let Next revalidate it hourly so a fresh deploy
// or cron run shows up without a redeploy. (Detail pages fetch fully live.)
export const revalidate = 3600;

export default async function HomePage() {
  const { data, error } = await supabase
    .from("releases")
    .select("*")
    .order("profit", { ascending: false });

  if (error) {
    return (
      <main className="container">
        <p className="empty">Could not load releases: {error.message}</p>
      </main>
    );
  }

  const releases = (data ?? []) as Release[];

  return (
    <main className="container">
      {releases.length === 0 ? (
        <p className="empty">
          No profitable upcoming releases right now. The list refreshes daily.
        </p>
      ) : (
        <ReleaseList releases={releases} />
      )}
    </main>
  );
}
