import Link from "next/link";
import { localeMeta, type Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { siteConfig } from "@/lib/site-config";
import { CheckCircleIcon } from "./icons";

const linkClass = "rounded text-muted-foreground hover:text-foreground hover:underline";

export function Footer({ locale, t }: { locale: Locale; t: Dictionary }) {
  const { social, features, trust } = siteConfig;
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
      <div className="mx-auto flex max-w-6xl flex-col gap-2 border-t border-border px-4 py-3 text-xs sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          {(social.instagramUrl || social.whatsappUrl) && (
            <ul aria-label={t.footer.social} className="flex gap-3">
              {social.instagramUrl && <li><a href={social.instagramUrl} rel="noopener noreferrer" className={linkClass}>{t.footer.instagram}</a></li>}
              {social.whatsappUrl && <li><a href={social.whatsappUrl} rel="noopener noreferrer" className={linkClass}>{t.footer.whatsapp}</a></li>}
            </ul>
          )}
          {trust.length > 0 && (
            <ul aria-label={t.footer.trust} className="flex gap-3">
              {trust.map((badge) => (
                <li key={badge.id}>
                  {badge.href ? <a href={badge.href} rel="noopener noreferrer" className={linkClass}>{badge.label[locale]}</a> : badge.label[locale]}
                </li>
              ))}
            </ul>
          )}
        </div>
        <p className="text-muted-foreground">© {year} {siteConfig.name}. {t.footer.rights}</p>
      </div>
    </footer>
  );
}
