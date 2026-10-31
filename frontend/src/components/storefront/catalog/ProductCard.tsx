import Image from "next/image";
import Link from "next/link";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { type CatalogImage, type ProductCardData } from "@/lib/catalog";
import { formatCurrency } from "@/lib/format";

/** Shows real prices only: a struck-through original appears solely when the backend sends a sale_price. */
export function Price({
  price,
  salePrice,
  locale,
  t,
  className = "",
}: {
  price: string;
  salePrice: string | null;
  locale: Locale;
  t: Dictionary;
  className?: string;
}) {
  return (
    <p className={"flex flex-wrap items-baseline gap-x-2 " + className}>
      {salePrice ? (
        <>
          <span className="font-medium">
            <span className="sr-only">{t.catalog.salePrice}: </span>
            {formatCurrency(salePrice, locale)}
          </span>
          <del className="text-sm text-muted-foreground">
            <span className="sr-only">{t.catalog.originalPrice}: </span>
            {formatCurrency(price, locale)}
          </del>
        </>
      ) : (
        <span className="font-medium">{formatCurrency(price, locale)}</span>
      )}
    </p>
  );
}

/**
 * Catalog media is stored as WebP under the same-origin /media/ path in the
 * production topology. Next Image now generates responsive, resized cached
 * variants instead of transferring the original upload to every viewport.
 */
export function CatalogPicture({
  image,
  fallbackAlt,
  sizes,
  eager,
  noImage,
}: {
  image: CatalogImage | null;
  fallbackAlt: string;
  sizes: string;
  eager?: boolean;
  noImage: string;
}) {
  return (
    <div className="relative aspect-[3/4] overflow-hidden rounded-lg bg-muted">
      {image ? (
        <Image
          src={image.url}
          alt={image.alt_text || fallbackAlt}
          fill
          sizes={sizes}
          quality={75}
          loading={eager ? "eager" : "lazy"}
          fetchPriority={eager ? "high" : "auto"}
          className="object-cover transition-transform duration-200 motion-reduce:transition-none group-hover:scale-[1.02]"
        />
      ) : (
        <span className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
          {noImage}
        </span>
      )}
    </div>
  );
}

export function ProductCard({
  product,
  locale,
  t,
  eager,
}: {
  product: ProductCardData;
  locale: Locale;
  t: Dictionary;
  eager?: boolean;
}) {
  return (
    <li>
      <Link
        href={"/" + locale + "/products/" + product.slug}
        className="group block rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
      >
        <CatalogPicture
          image={product.image}
          fallbackAlt={product.name}
          sizes="(min-width:1024px) 20vw, (min-width:640px) 33vw, 50vw"
          eager={eager}
          noImage={t.catalog.noImage}
        />
        <h3 className="mt-3 line-clamp-2 text-sm font-medium">{product.name}</h3>
        {product.code && <p className="mt-1 text-xs text-muted-foreground">کد محصول: {product.code}</p>}
        <Price
          price={product.price}
          salePrice={product.sale_price}
          locale={locale}
          t={t}
          className="mt-1 text-sm"
        />
        <p className={"mt-1 text-xs " + (product.in_stock ? "text-muted-foreground" : "font-medium text-foreground")}>
          {product.in_stock ? t.catalog.inStock : t.catalog.outOfStock}
        </p>
        {product.colors.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1.5" aria-label={t.catalog.availableColors}>
            {product.colors.map((c) => (
              <li key={c.slug}>
                <span
                  aria-hidden="true"
                  title={c.name}
                  className="block size-3.5 rounded-full border border-border"
                  style={c.hex_color ? { backgroundColor: c.hex_color } : undefined}
                />
                <span className="sr-only">{c.name}</span>
              </li>
            ))}
          </ul>
        )}
      </Link>
    </li>
  );
}
