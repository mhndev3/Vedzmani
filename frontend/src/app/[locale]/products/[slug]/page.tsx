import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getProduct, type ProductDetail } from "@/lib/catalog";
import { Price } from "@/components/storefront/catalog/ProductCard";
import { AddToCart } from "@/components/storefront/cart/AddToCart";
import { ProductGallery } from "@/components/storefront/product/ProductGallery";

type Props = {
  params: Promise<{ locale: string; slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Pick<Props, "params">): Promise<Metadata> {
  const { locale, slug } = await params;
  if (!isLocale(locale)) return {};
  try {
    const product = await getProduct(slug);
    return { title: product?.name ?? getDictionary(locale).product.notFoundTitle };
  } catch {
    return {};
  }
}

export default async function ProductPage({ params, searchParams }: Props) {
  const { locale, slug } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  const colorParam = (await searchParams).color;

  let product: ProductDetail | null = null;
  let failed = false;
  try {
    product = await getProduct(slug);
  } catch {
    failed = true;
  }
  if (!failed && !product) notFound();

  const backLink = (
    <Link
      href={`/${locale}/products`}
      className="inline-flex items-center rounded-lg text-sm text-muted-foreground hover:text-foreground"
    >
      <span aria-hidden="true" className="me-1 rtl:rotate-180">
        ←
      </span>
      {t.product.back}
    </Link>
  );

  if (failed || !product) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        {backLink}
        <div role="alert" className="mt-6 rounded-lg border border-border bg-muted p-8 text-center">
          <h1 className="font-medium">{t.catalog.errorTitle}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{t.catalog.errorText}</p>
          <Link
            href={`/${locale}/products/${slug}`}
            className="mt-4 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground"
          >
            {t.catalog.retry}
          </Link>
        </div>
      </div>
    );
  }

  // Color is URL state (?color=slug); unknown or absent falls back to the first variant.
  const wanted = Array.isArray(colorParam) ? colorParam[0] : colorParam;
  const color = product.colors.find((c) => c.slug === wanted) ?? product.colors[0] ?? null;
  const images = color
    ? [...color.images].sort((a, b) => Number(b.is_primary) - Number(a.is_primary) || a.position - b.position)
    : [];
  const inStock = !!color?.sizes.some((s) => s.in_stock);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <nav aria-label={t.product.breadcrumb} className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {backLink}
        <Link
          href={"/" + locale + "/categories/" + encodeURIComponent(product.category.slug)}
          className="rounded-lg text-sm text-muted-foreground hover:text-foreground"
        >
          {product.category.name}
        </Link>
      </nav>

      <div className="mt-6 grid gap-8 md:grid-cols-2">
        <ProductGallery
          images={images}
          productName={product.name}
          colorName={color?.name ?? ""}
          variantKey={color?.slug ?? "none"}
          labels={{
            gallery: t.product.gallery,
            previous: t.product.galleryPrevious,
            next: t.product.galleryNext,
            slide: t.product.gallerySlide,
            noImages: t.product.noImages,
          }}
        />

        <section className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{product.name}</h1>
          {product.code && <p className="mt-1 text-sm text-muted-foreground">کد محصول: {product.code}</p>}
          <Price
            price={product.price}
            salePrice={product.sale_price}
            locale={locale}
            t={t}
            className="mt-3 text-lg"
          />
          {color && (
            <p className={`mt-2 text-sm ${inStock ? "text-muted-foreground" : "font-medium"}`}>
              {inStock ? t.catalog.inStock : t.catalog.outOfStock}
            </p>
          )}

          {product.colors.length > 0 && color && (
            <div className="mt-6">
              <h2 className="text-sm font-semibold">
                {t.product.colors}: <span className="font-normal">{color.name}</span>
              </h2>
              <ul className="mt-2 flex flex-wrap gap-2">
                {product.colors.map((c) => {
                  const current = c.slug === color.slug;
                  return (
                    <li key={c.slug}>
                      <Link
                        href={`/${locale}/products/${product.slug}?color=${encodeURIComponent(c.slug)}`}
                        prefetch={false}
                        scroll={false}
                        aria-current={current ? "true" : undefined}
                        className={`inline-flex h-10 items-center gap-2 rounded-lg border px-3 text-sm ${
                          current ? "border-primary ring-1 ring-primary" : "border-border hover:bg-muted"
                        }`}
                      >
                        <span
                          aria-hidden="true"
                          className="size-4 rounded-full border border-border"
                          style={c.hex_color ? { backgroundColor: c.hex_color } : undefined}
                        />
                        {c.name}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {color &&
            (color.sizes.length > 0 ? (
              <AddToCart
                key={color.slug}
                locale={locale}
                sizes={color.sizes.map((s) => ({
                  id: s.id,
                  label: s.label,
                  in_stock: s.in_stock,
                  stock_quantity: s.stock_quantity,
                  measurements: s.measurements,
                }))}
                labels={{
                  sizes: t.product.sizes,
                  sizeOutOfStock: t.product.sizeOutOfStock,
                  addToCart: t.product.addToCart,
                  adding: t.product.adding,
                  added: t.product.added,
                  viewCart: t.product.viewCart,
                  sizeRequired: t.product.sizeRequired,
                  sizeMeasurements: t.product.sizeMeasurements,
                }}
                errors={t.cart.errors}
              />
            ) : (
              <div className="mt-6">
                <h2 className="text-sm font-semibold">{t.product.sizes}</h2>
                <p className="mt-2 text-sm text-muted-foreground">{t.product.noSizes}</p>
              </div>
            ))}

          {product.description.trim() && (
            <div className="mt-8 border-t border-border pt-6">
              <h2 className="text-sm font-semibold">{t.product.description}</h2>
              <p className="mt-2 whitespace-pre-line text-sm leading-7 text-muted-foreground">
                {product.description}
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
