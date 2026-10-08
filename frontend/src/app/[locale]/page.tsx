import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getHomepageSections } from "@/lib/homepage";
import { HomeSection } from "@/components/storefront/HomeSection";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  const sections = await getHomepageSections();

  return (
    <>
      <section className="border-b border-border bg-muted">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:py-24">
          <h1 className="max-w-2xl text-3xl font-semibold tracking-tight sm:text-5xl">
            {t.home.heroTitle}
          </h1>
          <p className="mt-4 max-w-xl text-muted-foreground">{t.home.heroText}</p>
        </div>
      </section>
      {sections.map((section) => (
        <HomeSection key={section.id} section={section} t={t} />
      ))}
    </>
  );
}
