import Link from "next/link";
import { localeMeta, type Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { siteConfig } from "@/lib/site-config";
import { CheckCircleIcon } from "./icons";
import { EnamadSeal } from "./EnamadSeal";

const linkClass = "rounded text-muted-foreground hover:text-foreground hover:underline";
const instagramUrl = "https://www.instagram.com/vedzmani/";

function InstagramIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      width={32}
      height={32}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
    >
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.5" cy="6.5" r=".8" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function Footer({ locale, t }: { locale: Locale; t: Dictionary }) {
  const { social, features } = siteConfig;
  const year = new Intl.NumberFormat(localeMeta[locale].numberLocale, { useGrouping: false }).format(new Date().getFullYear());

  return (
    <footer className="mt-10 border-t border-border bg-muted">
      {features.length > 0 && (
        <ul className="mx-auto grid max-w-6xl grid-cols-2 gap-3 border-b border-border px-4 py-3 text-xs sm:grid-cols-4">
          {features.map((feature) => (
            <li key={feature.id} className="flex items-center gap-2">
              <CheckCircleIcon />
              {feature.label[locale]}
            </li>
          ))}
        </ul>
      )}
      <nav aria-label={t.a11y.footerNav} className="mx-auto grid max-w-6xl grid-cols-2 gap-5 px-4 py-5">
        <div>
          <h2 className="mb-2 text-sm font-semibold">{t.footer.store}</h2>
          <ul className="space-y-1.5 text-xs">
            <li><Link href={`/${locale}/about`} className={linkClass}>{t.nav.about}</Link></li>
            <li><Link href={`/${locale}/faq`} className={linkClass}>{t.nav.faq}</Link></li>
          </ul>
        </div>
        <div>
          <h2 className="mb-2 text-sm font-semibold">{t.footer.customerService}</h2>
          <ul className="space-y-1.5 text-xs">
            <li><Link href={`/${locale}/support`} className={linkClass}>{t.nav.support}</Link></li>
          </ul>
        </div>
      </nav>

      <div dir="rtl" className="mx-auto flex max-w-6xl flex-row items-center justify-between gap-4 border-t border-border px-4 py-6">
        <section aria-label={locale === "fa" ? "اینستاگرام ودزمانی" : "Vedzmani on Instagram"} className="flex shrink-0 items-center">
          <a
            href={instagramUrl}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="VEDZMANI on Instagram"
            className="inline-flex min-h-12 min-w-12 items-center justify-center rounded-md text-foreground transition-colors hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
          >
            <InstagramIcon />
          </a>
        </section>

        <section
          aria-label={locale === "fa" ? "نماد اعتماد الکترونیکی" : "Electronic trust seal"}
          className="flex shrink-0 items-center justify-center"
        >
          <EnamadSeal />
        </section>
      </div>

      <div className="mx-auto flex max-w-6xl flex-col gap-2 border-t border-border px-4 py-3 text-xs sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          {social.whatsappUrl && (
            <ul aria-label={t.footer.social} className="flex gap-3">
              <li><a href={social.whatsappUrl} rel="noopener noreferrer" className={linkClass}>{t.footer.whatsapp}</a></li>
            </ul>
          )}
        </div>
        <p className="text-muted-foreground">© {year} {siteConfig.name}. {t.footer.rights}</p>
      </div>
    </footer>
  );
}
