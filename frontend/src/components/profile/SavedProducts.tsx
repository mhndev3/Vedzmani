"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ProductCard } from "@/components/storefront/catalog/ProductCard";
import { CarouselTrack } from "@/components/storefront/CarouselTrack";
import { apiRequest } from "@/lib/browser-api";

type FavoriteCard = {
  id: number;
  variant_id: number;
  name: string;
  slug: string;
  code: string | null;
  price: string;
  sale_price: string | null;
  category: { name: string; slug: string };
  color: { name: string; slug: string; hex_color: string | null };
  in_stock: boolean;
  image: {
    url: string;
    thumbnail_url?: string;
    display_url?: string;
    alt_text: string;
    width: number;
    height: number;
  } | null;
};

type Favorite = {
  product_id: number;
  product_slug: string;
  product_name: string;
  card: FavoriteCard | null;
};

export function SavedProducts({ locale, t }: { locale: Locale; t: Dictionary }) {
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

  function removeButton(item: Favorite) {
    return (
      <button
        type="button"
        onClick={() => void remove(item.product_slug)}
        disabled={removing !== null}
        aria-label={`حذف ${item.product_name} از نشان‌شده‌ها`}
        title="حذف از نشان‌شده‌ها"
        className="inline-flex size-9 items-center justify-center rounded-full border border-border bg-card/95 text-foreground shadow-md backdrop-blur transition hover:border-destructive/50 hover:bg-destructive hover:text-destructive-foreground disabled:cursor-not-allowed disabled:opacity-60"
      >
        {removing === item.product_slug ? (
          <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
        ) : (
          <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none">
            <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        )}
      </button>
    );
  }

  const useCarousel = items.length > 2;

  return (
    <section className="mt-8 rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="saved-products-title">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <h2 id="saved-products-title" className="text-lg font-semibold">نشان‌شده‌ها</h2>
          {!loading && items.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">{items.length.toLocaleString("fa-IR")} محصول</p>
          )}
        </div>
      </div>

      {loading ? (
        <p className="py-6 text-sm text-muted-foreground">در حال بارگذاری…</p>
      ) : items.length ? (
        useCarousel ? (
          <CarouselTrack itemCount={items.length} ariaLabel="محصولات نشان‌شده">
            {items.map((item, index) => item.card ? (
              <ProductCard
                key={item.product_id}
                product={item.card}
                locale={locale}
                t={t}
                eager={index === 0}
                variant="carousel-wide"
                removeAction={removeButton(item)}
              />
            ) : (
              <li key={item.product_id} className="relative min-w-0 shrink-0 basis-[70%] snap-start sm:basis-[40%] lg:basis-[calc(50%-8px)]">
                <div className="h-full rounded-2xl border border-border bg-card p-4 pt-14 shadow-sm">
                  <div className="absolute end-4 top-4 z-20">{removeButton(item)}</div>
                  <Link href={`/${locale}/products/${item.product_slug}`} className="font-semibold hover:underline">
                    {item.product_name}
                  </Link>
                </div>
              </li>
            ))}
          </CarouselTrack>
        ) : (
          <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {items.map((item, index) => item.card ? (
              <ProductCard
                key={item.product_id}
                product={item.card}
                locale={locale}
                t={t}
                eager={index === 0}
                removeAction={removeButton(item)}
              />
            ) : (
              <li key={item.product_id} className="relative min-w-0">
                <div className="h-full rounded-2xl border border-border bg-card p-4 pt-14 shadow-sm">
                  <div className="absolute end-4 top-4 z-20">{removeButton(item)}</div>
                  <Link href={`/${locale}/products/${item.product_slug}`} className="font-semibold hover:underline">
                    {item.product_name}
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )
      ) : (
        <p className="rounded-xl border border-dashed border-border bg-muted/40 px-4 py-8 text-center text-sm text-muted-foreground">
          هنوز محصولی نشان نکرده‌اید.
        </p>
      )}

      {message && <p role="status" className="mt-3 text-xs text-muted-foreground">{message}</p>}
    </section>
  );
}
