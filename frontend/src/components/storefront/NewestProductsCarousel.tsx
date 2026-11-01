"use client";

import Link from "next/link";
import { useRef } from "react";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ProductCard } from "@/components/storefront/catalog/ProductCard";
import type { ProductCardData } from "@/lib/catalog";

export function NewestProductsCarousel({
  locale, t, products, emptyText, title,
}: {
  locale: Locale;
  t: Dictionary;
  products: ProductCardData[];
  emptyText: string;
  title: string;
}) {
  const track = useRef<HTMLUListElement>(null);

  function scroll(direction: "previous" | "next") {
    const element = track.current;
    if (!element) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const distance = Math.max(220, Math.round(element.clientWidth * 0.82));
    element.scrollBy({
      left: direction === "next" ? -distance : distance,
      behavior: reducedMotion ? "auto" : "smooth",
    });
  }

  return (
    <section aria-labelledby="home-newest-products" className="mx-auto max-w-6xl px-4 py-10 sm:py-12">
      <div className="mb-5 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="mb-1 text-xs font-medium tracking-wide text-muted-foreground">تازه‌های فروشگاه</p>
          <h2 id="home-newest-products" className="text-xl font-bold tracking-tight sm:text-2xl">{title}</h2>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => scroll("previous")}
            disabled={products.length < 2}
            aria-label="محصولات قبلی"
            className="inline-flex size-10 items-center justify-center rounded-full border border-border bg-card shadow-sm transition hover:border-primary/40 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none">
              <path d="m14.5 5-7 7 7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => scroll("next")}
            disabled={products.length < 2}
            aria-label="محصولات بعدی"
            className="inline-flex size-10 items-center justify-center rounded-full border border-border bg-card shadow-sm transition hover:border-primary/40 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none">
              <path d="m9.5 5 7 7-7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <Link
            href={`/${locale}/products`}
            prefetch={false}
            className="hidden h-10 items-center rounded-full border border-border bg-card px-4 text-sm font-semibold transition hover:bg-muted sm:inline-flex"
          >
            مشاهده همه
          </Link>
        </div>
      </div>
      {products.length ? (
        <>
          <ul
            ref={track}
            dir="rtl"
            className="flex snap-x snap-mandatory gap-3 overflow-x-auto overscroll-x-contain scroll-px-1 pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:gap-4"
          >
            {products.map((product, index) => (
              <ProductCard key={product.id} product={product} locale={locale} t={t} eager={index < 2} variant="carousel" />
            ))}
          </ul>
          <div className="mt-1 flex justify-center sm:hidden">
            <Link
              href={`/${locale}/products`}
              prefetch={false}
              className="inline-flex h-10 items-center rounded-full border border-border bg-card px-5 text-sm font-semibold transition hover:bg-muted"
            >
              مشاهده همه محصولات
            </Link>
          </div>
        </>
      ) : (
        <p className="rounded-2xl border border-dashed border-border bg-muted/60 px-4 py-10 text-center text-sm text-muted-foreground">
          {emptyText}
        </p>
      )}
    </section>
  );
}
