import Link from "next/link";
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
  return (
    <section aria-labelledby="home-newest-products" className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 id="home-newest-products" className="text-xl font-semibold tracking-tight">{title}</h2>
        <Link
          href={`/${locale}/products`}
          className="inline-flex h-9 items-center rounded-full border border-border bg-card px-4 text-sm font-medium shadow-sm transition hover:-translate-y-0.5 hover:bg-muted"
        >
          مشاهده همه
        </Link>
      </div>
      {products.length ? (
        <ul className="flex snap-x snap-mandatory gap-3 overflow-x-auto overscroll-x-contain pb-4 sm:gap-4">
          {products.map((product, index) => (
            <ProductCard key={product.id} product={product} locale={locale} t={t} eager={index < 2} variant="carousel" />
          ))}
        </ul>
      ) : (
        <p className="rounded-2xl border border-dashed border-border bg-muted/60 px-4 py-10 text-center text-sm text-muted-foreground">
          {emptyText}
        </p>
      )}
    </section>
  );
}
