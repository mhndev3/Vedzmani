import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getHomepageSections } from "@/lib/homepage";
import { HomeSection } from "@/components/storefront/HomeSection";
import { HomepageHeroSlider } from "@/components/storefront/HomepageHeroSlider";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  const sections = await getHomepageSections();

  return (
    <>
      <HomepageHeroSlider locale={locale} />
      {sections.map((section) => (
        <HomeSection key={section.id} section={section} t={t} />
      ))}
    </>
  );
}
