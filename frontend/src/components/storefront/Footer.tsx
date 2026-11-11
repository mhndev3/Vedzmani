import Link from "next/link";
import { localeMeta, type Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { siteConfig } from "@/lib/site-config";
import { CheckCircleIcon } from "./icons";

const linkClass = "rounded text-muted-foreground hover:text-foreground hover:underline";
const instagramUrl = "https://www.instagram.com/vedzmani/";
const enamadUrl = "https://trustseal.enamad.ir/?id=8480737&Code=hThQ5QKm0EhDkGtXcKiXmh0BBbXTcwgm";
const enamadLogoUrl = "https://trustseal.enamad.ir/logo.aspx?id=8480737&Code=hThQ5QKm0EhDkGtXcKiXmh0BBbXTcwgm";

function InstagramIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      width={23}
      height={23}
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

      <div dir="rtl" className="mx-auto flex max-w-6xl flex-col gap-6 border-t border-border px-4 py-6 sm:flex-row sm:items-center sm:justify-between">
        <section aria-labelledby="footer-instagram-title" className="flex flex-col items-start gap-2">
          <h2 id="footer-instagram-title" className="text-sm font-semibold text-foreground">
            {locale === "fa" ? "اینستاگرام ودزمانی" : "Vedzmani on Instagram"}
          </h2>
          <a
            href={instagramUrl}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="VEDZMANI on Instagram"
            className="inline-flex min-h-11 items-center gap-2 rounded-md text-base font-bold tracking-wide text-foreground transition-colors hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring sm:text-lg"
          >
            <InstagramIcon />
            <span>VEDZMANI</span>
          </a>
        </section>

        <a
          href={enamadUrl}
          target="_blank"
          rel="noopener noreferrer"
          referrerPolicy="origin"
          aria-label={locale === "fa" ? "مشاهده نماد اعتماد الکترونیکی ودزمانی" : "View Vedzmani electronic trust seal"}
          className="inline-flex w-fit items-center justify-center rounded-md bg-background p-2 transition-shadow hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
        >
          <img
            referrerPolicy="origin"
            src={enamadLogoUrl}
            alt=""
            code="hThQ5QKm0EhDkGtXcKiXmh0BBbXTcwgm"
            width={100}
            height={100}
            style={{ cursor: "pointer" }}
            className="h-auto w-[88px] object-contain sm:w-[100px]"
          />
        </a>
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
