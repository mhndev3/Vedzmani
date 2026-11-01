"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Locale } from "@/i18n/config";
import { apiRequest } from "@/lib/browser-api";

type Favorite = { product_id: number; product_slug: string; product_name: string };

export function SavedProducts({ locale }: { locale: Locale }) {
  const [items, setItems] = useState<Favorite[]>([]);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    apiRequest<Favorite[]>("GET", "/api/catalog/favorites/")
      .then((rows) => { if (active) setItems(rows); })
      .catch(() => { if (active) setItems([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function remove(slug: string) {
    if (removing) return;
    setRemoving(slug);
    setMessage("");
    try {
      await apiRequest("DELETE", `/api/catalog/favorites/${encodeURIComponent(slug)}/`);
      setItems((current) => current.filter((item) => item.product_slug !== slug));
      setMessage("محصول از نشان‌شده‌ها حذف شد.");
    } catch {
      setMessage("حذف محصول انجام نشد. دوباره تلاش کنید.");
    } finally {
      setRemoving(null);
    }
  }

  return (
    <section className="mt-8 rounded-2xl border border-border bg-card p-5 shadow-sm" aria-labelledby="saved-products-title">
      <h2 id="saved-products-title" className="text-lg font-semibold">نشان‌شده‌ها</h2>
      {loading ? <p className="mt-3 text-sm text-muted-foreground">در حال بارگذاری…</p> :
        items.length ? (
          <ul className="mt-3 divide-y divide-border">
            {items.map((item) => (
              <li key={item.product_id} className="flex items-center justify-between gap-3 py-3">
                <Link href={`/${locale}/products/${item.product_slug}`} className="min-w-0 font-medium transition hover:text-muted-foreground">{item.product_name}</Link>
                <button type="button" onClick={() => void remove(item.product_slug)} disabled={removing !== null}
                  className="shrink-0 rounded-full border border-border px-3 py-1.5 text-xs transition hover:bg-muted disabled:opacity-60">
                  {removing === item.product_slug ? "در حال حذف…" : "حذف"}
                </button>
              </li>
            ))}
          </ul>
        ) : <p className="mt-3 text-sm text-muted-foreground">هنوز محصولی نشان نکرده‌اید.</p>}
      {message && <p role="status" className="mt-2 text-xs text-muted-foreground">{message}</p>}
    </section>
  );
}
