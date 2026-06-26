import { createClient } from "@supabase/supabase-js";

// Public, read-only client. The anon key is safe to expose; RLS limits it to
// SELECT on the `releases` table (see supabase/schema.sql).
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  // Surfaced at build/runtime so a misconfigured deploy fails loudly rather than
  // silently returning an empty list.
  throw new Error(
    "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY env vars."
  );
}

export const supabase = createClient(url, anonKey, {
  auth: { persistSession: false },
});
