import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getHomepageContent } from "@/lib/homepage";
import { HomeCategoryGrid } from "@/components/storefront/HomeCategoryGrid";
import { HomepageHeroSlider } from "@/components/storefront/HomepageHeroSlider";
import { NewestProductsCarousel } from "@/components/storefront/NewestProductsCarousel";
import { AdminStorefrontMode, AdminStorefrontSection } from "@/components/admin/AdminStorefrontMode";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  const content = await getHomepageContent();

  return (
    <AdminStorefrontMode locale={locale}>
      <HomepageHeroSlider banners={content.banners} locale={locale} />
      {content.sections.length > 0 ? content.sections.map((section) => (
        section.section_type === "categories" ? (
          <AdminStorefrontSection key={section.id} section={{ id: section.id, title: section.title, eyebrow: section.eyebrow, show_view_all: section.show_view_all, view_all_url: section.view_all_url }}>
            <HomeCategoryGrid sectionId={`home-categories-${section.id}`} locale={locale} categories={section.categories} title={section.title} eyebrow={section.eyebrow} />
          </AdminStorefrontSection>
        ) : (
          <AdminStorefrontSection key={section.id} section={{ id: section.id, title: section.title, eyebrow: section.eyebrow, show_view_all: section.show_view_all, view_all_url: section.view_all_url }}>
          <NewestProductsCarousel
            sectionId={`home-newest-products-${section.id}`}
            locale={locale}
            t={t}
            products={section.products}
            emptyText={t.home.emptySection}
            title={section.title}
            eyebrow={section.eyebrow}
            viewAllHref={section.show_view_all && section.view_all_url ? (section.view_all_url.startsWith(`/${locale}/`) ? section.view_all_url : `/${locale}${section.view_all_url}`) : undefined}
            showViewAll={section.show_view_all}
          />
          </AdminStorefrontSection>
        )
      )) : (
        <>
          <HomeCategoryGrid locale={locale} categories={content.categories} />
          <NewestProductsCarousel locale={locale} t={t} products={content.newestProducts} emptyText={t.home.emptySection} title={t.home.sections.newestProducts} />
        </>
      )}
    </AdminStorefrontMode>
  );
}
