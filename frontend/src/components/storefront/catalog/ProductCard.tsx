import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { type CatalogImage, type ProductCardData } from "@/lib/catalog";
import { formatCurrency } from "@/lib/format";
import { ColorSwatch } from "./ColorSwatch";

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
 * Product media is served directly by Nginx from the shared /media volume and
 * is already WebP with immutable cache headers. Keep it unoptimized until the
 * Next image optimizer has an explicit internal route to that Nginx media path.
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
    <div className="relative aspect-[3/4] overflow-hidden rounded-xl bg-muted">
      {image ? (
        <Image
          src={image.thumbnail_url || image.url}
          alt={image.alt_text || fallbackAlt}
          fill
          sizes={sizes}
          unoptimized
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
  variant = "grid",
  removeAction,
  "aria-hidden": ariaHidden,
  inert,
}: {
  product: ProductCardData;
  locale: Locale;
  t: Dictionary;
  eager?: boolean;
  variant?: "grid" | "carousel" | "carousel-wide";
  removeAction?: ReactNode;
  "aria-hidden"?: boolean;
  inert?: boolean;
}) {
  const variantClass = variant === "carousel"
    ? "min-w-0 shrink-0 basis-[70%] snap-start sm:basis-[40%] lg:basis-[calc(25%-12px)]"
    : variant === "carousel-wide"
      ? "min-w-0 shrink-0 basis-[70%] snap-start sm:basis-[40%] lg:basis-[calc(50%-8px)]"
      : "min-w-0";

  return (
    <li className={variantClass + " relative"} aria-hidden={ariaHidden} inert={inert}>
      {removeAction && <div className="absolute end-4 top-4 z-20">{removeAction}</div>}
      <Link
        href={"/" + locale + "/products/" + product.slug + "/" + encodeURIComponent(product.color.slug)}
        prefetch={false}
        className="group block h-full rounded-2xl border border-border bg-card p-2.5 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-primary/30 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
      >
        <CatalogPicture
          image={product.image}
          fallbackAlt={product.name}
          sizes="(min-width:1024px) 20vw, (min-width:640px) 33vw, 50vw"
          eager={eager}
          noImage={t.catalog.noImage}
        />
        <h3 className="mt-3 line-clamp-2 min-h-10 text-sm font-semibold">{product.name}</h3>
        <p className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          <ColorSwatch name={product.color.name} hexColor={product.color.hex_color} productCode={product.code} colorIndex={0} />
          <span>{product.color.name}</span>
        </p>
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
      </Link>
    </li>
  );
}
