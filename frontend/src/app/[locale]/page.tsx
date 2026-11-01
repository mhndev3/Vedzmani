import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getHomepageContent } from "@/lib/homepage";
import { HomeCategoryGrid } from "@/components/storefront/HomeCategoryGrid";
import { HomepageHeroSlider } from "@/components/storefront/HomepageHeroSlider";
import { NewestProductsCarousel } from "@/components/storefront/NewestProductsCarousel";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  const { categories, newestProducts } = await getHomepageContent();

  return (
    <>
      <HomepageHeroSlider />
      <HomeCategoryGrid locale={locale} categories={categories} />
      <NewestProductsCarousel locale={locale} t={t} products={newestProducts} emptyText={t.home.emptySection} title={t.home.sections.newestProducts} />
    </>
  );
}
