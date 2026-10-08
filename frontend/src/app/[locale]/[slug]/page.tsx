import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { isLocale, locales } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

const slugs = ["about", "contact", "returns", "faq", "support"] as const;
type Slug = (typeof slugs)[number];
const isSlug = (v: string): v is Slug => (slugs as readonly string[]).includes(v);

export const dynamicParams = false;

export function generateStaticParams() {
  return locales.flatMap((locale) => slugs.map((slug) => ({ locale, slug })));
}

type Props = { params: Promise<{ locale: string; slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, slug } = await params;
  if (!isLocale(locale) || !isSlug(slug)) return {};
  return { title: getDictionary(locale).pages[slug] };
}

/** Honest placeholder boundary for the static info pages until real content exists. */
export default async function InfoPage({ params }: Props) {
  const { locale, slug } = await params;
  if (!isLocale(locale) || !isSlug(slug)) notFound();
  const t = getDictionary(locale);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">{t.pages[slug]}</h1>
      <p className="mt-4 text-muted-foreground">{t.pages.placeholder}</p>
    </div>
  );
}
