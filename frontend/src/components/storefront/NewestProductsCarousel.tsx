import Link from "next/link";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ProductCard } from "@/components/storefront/catalog/ProductCard";
import { CarouselTrack } from "@/components/storefront/CarouselTrack";
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
    <section aria-labelledby="home-newest-products" className="mx-auto max-w-6xl px-4 py-10 sm:py-12">
      <div className="mb-5 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="mb-1 text-xs font-medium tracking-wide text-muted-foreground">تازه‌های فروشگاه</p>
          <h2 id="home-newest-products" className="text-xl font-bold tracking-tight sm:text-2xl">{title}</h2>
        </div>
        <Link
          href={`/${locale}/products`}
          prefetch={false}
          className="inline-flex h-10 shrink-0 items-center rounded-full border border-border bg-card px-4 text-sm font-semibold transition hover:bg-muted"
        >
          مشاهده همه
        </Link>
      </div>
      {products.length ? (
        <CarouselTrack itemCount={products.length}>
          {products.map((product, index) => (
            <ProductCard key={product.id} product={product} locale={locale} t={t} eager={index === 0} variant="carousel" />
          ))}
        </CarouselTrack>
      ) : (
        <p className="rounded-2xl border border-dashed border-border bg-muted/60 px-4 py-10 text-center text-sm text-muted-foreground">
          {emptyText}
        </p>
      )}
    </section>
  );
}
