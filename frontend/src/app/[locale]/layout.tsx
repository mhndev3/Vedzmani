import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { isLocale, locales, localeMeta } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { siteConfig } from "@/lib/site-config";
import { Footer } from "@/components/storefront/Footer";
import { Header } from "@/components/storefront/Header";
import { notFound } from "next/navigation";
import "../globals.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
};

/**
 * Indexing stays OFF (staging protection from the foundation) until
 * SITE_ALLOW_INDEXING=true is set at build time for production.
 */
const allowIndexing = process.env.SITE_ALLOW_INDEXING === "true";
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = getDictionary(locale);
  return {
    metadataBase: siteUrl ? new URL(siteUrl) : undefined,
    title: { default: t.meta.title, template: `%s | ${siteConfig.name}` },
    description: t.meta.description,
    ...(siteUrl && {
      alternates: { languages: { fa: "/fa", en: "/en" } },
    }),
    openGraph: {
      type: "website",
      siteName: siteConfig.name,
      locale: localeMeta[locale].ogLocale,
    },
    robots: allowIndexing ? { index: true, follow: true } : { index: false, follow: false },
  };
}

// Runs before first paint: stored choice, else system preference.
const themeScript = `(function(){try{var t=localStorage.getItem("theme");var d=t?t==="dark":matchMedia("(prefers-color-scheme: dark)").matches;if(d)document.documentElement.classList.add("dark")}catch(e){}})()`;

export default async function RootLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);

  return (
    <html lang={locale} dir={localeMeta[locale].dir} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="flex min-h-dvh flex-col bg-background text-foreground antialiased">
        <a
          href="#main"
          className="sr-only rounded-lg bg-primary px-4 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:z-50"
        >
          {t.a11y.skipToContent}
        </a>
        <Header locale={locale} t={t} />
        <main id="main" tabIndex={-1} className="flex-1 outline-none">
          {children}
        </main>
        <Footer locale={locale} t={t} />
      </body>
    </html>
  );
}
