import type { Metadata, Viewport } from "next";
import type { CSSProperties, ReactNode } from "react";
import { apiGet } from "@/lib/api";
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
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
};

/** Indexing remains disabled in development/preview builds. */
const allowIndexing = process.env.SITE_ALLOW_INDEXING === "true";
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://vedzmani.ir";
const organizationId = `${siteUrl}/#organization`;
const structuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": organizationId,
      name: "ودزمانی",
      alternateName: "Vedzmani",
      url: siteUrl,
    },
    {
      "@type": "WebSite",
      "@id": `${siteUrl}/#website`,
      url: siteUrl,
      name: "ودزمانی",
      alternateName: "Vedzmani",
      publisher: { "@id": organizationId },
      inLanguage: "fa-IR",
    },
  ],
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = getDictionary(locale);
  return {
    metadataBase: new URL(siteUrl),
    title: { default: t.meta.title, template: `%s | ${siteConfig.name}` },
    description: t.meta.description,
    applicationName: "Vedzmani",
    openGraph: {
      type: "website",
      siteName: "ودزمانی | Vedzmani",
      locale: localeMeta[locale].ogLocale,
    },
    robots: allowIndexing ? { index: true, follow: true } : { index: false, follow: false },
  };
}

// Runs before first paint: stored choice, else system preference.
const themeScript = `(function(){try{var t=localStorage.getItem("theme");var d=t?t==="dark":matchMedia("(prefers-color-scheme: dark)").matches;if(d)document.documentElement.classList.add("dark")}catch(e){}})()`;

type StorefrontThemeSettings = {
  primary: string;
  primary_foreground: string;
  accent: string;
  accent_foreground: string;
  font: "system" | "persian-modern" | "classic";
  radius: "compact" | "medium" | "rounded";
  motion: "none" | "subtle" | "standard";
};

const defaultTheme: StorefrontThemeSettings = {
  primary: "#171717",
  primary_foreground: "#fafafa",
  accent: "#e5e5e5",
  accent_foreground: "#171717",
  font: "system",
  radius: "medium",
  motion: "standard",
};

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
  let theme = defaultTheme;
  try {
    const response = await apiGet<{ settings: StorefrontThemeSettings }>("/api/catalog/storefront/theme/");
    theme = response.settings;
  } catch {
    // Keep the compiled default theme if the configuration API is unavailable.
  }

  const themeStyle = {
    "--store-primary": theme.primary,
    "--store-primary-foreground": theme.primary_foreground,
    "--store-accent": theme.accent,
    "--store-accent-foreground": theme.accent_foreground,
    "--store-radius": theme.radius === "compact" ? "0.35rem" : theme.radius === "rounded" ? "1rem" : "0.5rem",
    "--store-font-family": theme.font === "classic"
      ? '"Noto Naskh Arabic", Tahoma, serif'
      : theme.font === "persian-modern"
        ? 'Tahoma, "Noto Sans Arabic", sans-serif'
        : "var(--font-body)",
    "--store-motion-duration": theme.motion === "subtle" ? "180ms" : "280ms",
  } as CSSProperties;

  return (
    <html lang={locale} dir={localeMeta[locale].dir} data-motion={theme.motion} style={themeStyle} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }}
        />
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
