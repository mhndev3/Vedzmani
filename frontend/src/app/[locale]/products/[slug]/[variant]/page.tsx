import type { Metadata } from "next";
import { Suspense } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { isLocale, type Locale } from "@/i18n/config";
import { getDictionary, type Dictionary } from "@/i18n/dictionaries";
import { emptyState, getProduct, getProducts, type ProductDetail } from "@/lib/catalog";
import { Price, ProductCard } from "@/components/storefront/catalog/ProductCard";
import { ColorSwatch } from "@/components/storefront/catalog/ColorSwatch";
import { AddToCart } from "@/components/storefront/cart/AddToCart";
import { ProductGallery } from "@/components/storefront/product/ProductGallery";
import { ProductActions } from "@/components/storefront/product/ProductActions";

type Props = {
  params: Promise<{ locale: string; slug: string; variant: string }>;
};

async function RelatedProductsSection({
  product,
  locale,
  t,
}: {
  product: ProductDetail;
  locale: Locale;
  t: Dictionary;
}) {
  const response = await getProducts(
    { ...emptyState, category: [product.category.slug] },
    { cache: "force-cache", next: { revalidate: 60 } },
  ).catch(() => null);
  const relatedProducts = (response?.results ?? [])
    .filter((item) => item.id !== product.id)
    .slice(0, 4);

  if (relatedProducts.length === 0) return null;

  return (
    <section aria-labelledby="related-products-title" className="mt-12">
      <h2 id="related-products-title" className="mb-4 text-xl font-semibold tracking-tight">محصولات مشابه</h2>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {relatedProducts.map((item, index) => (
          <ProductCard key={item.variant_id} product={item} locale={locale} t={t} eager={index < 2} />
        ))}
      </ul>
    </section>
  );
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, slug } = await params;
  if (!isLocale(locale)) return {};
  try {
    const product = await getProduct(slug);
    return { title: product?.name ?? getDictionary(locale).product.notFoundTitle };
  } catch {
    return {};
  }
}

export default async function VariantProductPage({ params }: Props) {
  const { locale, slug, variant: variantSlug } = await params;
  if (!isLocale(locale)) notFound();

  const t = getDictionary(locale);
  let product: ProductDetail | null = null;
  let failed = false;
  try {
    product = await getProduct(slug);
  } catch {
    failed = true;
  }

  if (!failed && !product) notFound();
  if (failed || !product) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <Link href={"/" + locale + "/products"} prefetch={false} className="inline-flex items-center rounded-lg text-sm text-muted-foreground hover:text-foreground">
          <span aria-hidden="true" className="me-1 rtl:rotate-180">←</span>
          {t.product.back}
        </Link>
        <div role="alert" className="mt-6 rounded-lg border border-border bg-muted p-8 text-center">
          <h1 className="font-medium">{t.catalog.errorTitle}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{t.catalog.errorText}</p>
          <Link href={"/" + locale + "/products/" + slug + "/" + variantSlug} className="mt-4 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground">
            {t.catalog.retry}
          </Link>
        </div>
      </div>
    );
  }

  const color = product.colors.find((item) => item.slug === variantSlug);
  if (!color) notFound();

  const images = [...color.images].sort(
    (a, b) => Number(b.is_primary) - Number(a.is_primary) || a.position - b.position,
  );
  const inStock = color.sizes.some((size) => size.in_stock);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <nav aria-label={t.product.breadcrumb} className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Link href={"/" + locale + "/products"} prefetch={false} className="inline-flex items-center rounded-lg text-sm text-muted-foreground hover:text-foreground">
          <span aria-hidden="true" className="me-1 rtl:rotate-180">←</span>
          {t.product.back}
        </Link>
        <Link
          href={"/" + locale + "/categories/" + encodeURIComponent(product.category.slug)}
          prefetch={false}
          className="rounded-lg text-sm text-muted-foreground hover:text-foreground"
        >
          {product.category.name}
        </Link>
      </nav>

      <div className="mt-6 grid gap-8 md:grid-cols-2">
        <ProductGallery
          images={images}
          productName={product.name}
          colorName={color.name}
          variantKey={color.slug}
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
          <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
            <ColorSwatch name={color.name} hexColor={color.hex_color} className="size-4" />
            <span>{color.name}</span>
          </div>
          {color.product_code && (
            <p className="mt-1 text-sm text-muted-foreground">کد محصول: {color.product_code}</p>
          )}
          <Price
            price={product.price}
            salePrice={product.sale_price}
            locale={locale}
            t={t}
            className="mt-3 text-lg"
          />
          <p className={"mt-2 text-sm " + (inStock ? "text-muted-foreground" : "font-medium")}>
            {inStock ? t.catalog.inStock : t.catalog.outOfStock}
          </p>

          <ProductActions
            productId={product.id}
            productSlug={product.slug}
            productName={product.name}
            locale={locale}
            variantSlug={color.slug}
          />

          {color.sizes.length > 0 ? (
            <AddToCart
              key={color.slug}
              locale={locale}
              sizes={color.sizes.map((size) => ({
                id: size.id,
                sku: size.sku,
                label: size.label,
                in_stock: size.in_stock,
                stock_quantity: size.stock_quantity,
                measurements: size.measurements,
                description: size.size_description,
              }))}
              guestContext={{
                product: { id: product.id, name: product.name, slug: product.slug },
                color: { name: color.name, slug: color.slug, hex_color: color.hex_color },
                unit_price: product.sale_price ?? product.price,
                image: images[0] ? {
                  url: images[0].url,
                  thumbnail_url: images[0].thumbnail_url ?? images[0].url,
                  alt_text: images[0].alt_text || product.name,
                  width: images[0].width,
                  height: images[0].height,
                } : null,
              }}
              labels={{
                sizes: t.product.sizes,
                sizeOutOfStock: t.product.sizeOutOfStock,
                addToCart: t.product.addToCart,
                adding: t.product.adding,
                added: t.product.added,
                viewCart: t.product.viewCart,
                sizeRequired: t.product.sizeRequired,
                sizeMeasurements: t.product.sizeMeasurements,
                description: t.product.description,
              }}
              errors={t.cart.errors}
            />
          ) : (
            <div className="mt-6">
              <h2 className="text-sm font-semibold">{t.product.sizes}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{t.product.noSizes}</p>
            </div>
          )}

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

      <Suspense fallback={null}>
        <RelatedProductsSection product={product} locale={locale} t={t} />
      </Suspense>
    </div>
  );
}
