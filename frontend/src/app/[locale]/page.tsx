import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getHomepageContent } from "@/lib/homepage";
import { HomeCategoryGrid } from "@/components/storefront/HomeCategoryGrid";
import { HomepageHeroSlider } from "@/components/storefront/HomepageHeroSlider";
import { ProductCard } from "@/components/storefront/catalog/ProductCard";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  const { categories, newestProducts } = await getHomepageContent();

  return (
    <>
      <HomepageHeroSlider />
      <HomeCategoryGrid locale={locale} categories={categories} />
      <section aria-labelledby="home-newest-products" className="mx-auto max-w-6xl px-4 py-8">
        <h2 id="home-newest-products" className="mb-4 text-xl font-semibold tracking-tight">
          {t.home.sections.newestProducts}
        </h2>
        {newestProducts.length > 0 ? (
          <ul className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
            {newestProducts.map((product, index) => (
              <ProductCard
                key={product.id}
                product={product}
                locale={locale}
                t={t}
                eager={index < 2}
              />
            ))}
          </ul>
        ) : (
          <p className="rounded-lg border border-dashed border-border bg-muted px-4 py-10 text-center text-sm text-muted-foreground">
            {t.home.emptySection}
          </p>
        )}
      </section>
    </>
  );
}
