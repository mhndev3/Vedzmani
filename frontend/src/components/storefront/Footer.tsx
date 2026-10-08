import Link from "next/link";
import { localeMeta, type Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { siteConfig } from "@/lib/site-config";
import { CheckCircleIcon } from "./icons";

const linkClass = "rounded text-muted-foreground hover:text-foreground hover:underline";

function Column({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {children}
    </div>
  );
}

function LinkList({ links }: { links: { href: string; label: string }[] }) {
  return (
    <ul className="space-y-2 text-sm">
      {links.map((l) => (
        <li key={l.href}>
          <Link href={l.href} className={linkClass}>
            {l.label}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Server Component. Store facts come from siteConfig; empty values render nothing. */
export function Footer({ locale, t }: { locale: Locale; t: Dictionary }) {
  const { social, features, trust } = siteConfig;
  const year = new Intl.NumberFormat(localeMeta[locale].numberLocale, {
    useGrouping: false,
  }).format(new Date().getFullYear());
  const soon = <p className="text-sm text-muted-foreground">{t.footer.comingSoon}</p>;

  return (
    <footer className="mt-16 border-t border-border bg-muted">
      {features.length > 0 && (
        <ul className="mx-auto grid max-w-6xl grid-cols-2 gap-4 border-b border-border px-4 py-6 md:grid-cols-4">
          {features.map((f) => (
            <li key={f.id} className="flex items-center gap-2 text-sm">
              <CheckCircleIcon />
              {f.label[locale]}
            </li>
          ))}
        </ul>
      )}
      <nav
        aria-label={t.a11y.footerNav}
        className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:grid-cols-2 lg:grid-cols-4"
      >
        <Column title={t.footer.categories}>{soon}</Column>
        <Column title={t.footer.store}>
          <LinkList
            links={[
              { href: `/${locale}/about`, label: t.nav.about },
              { href: `/${locale}/contact`, label: t.nav.contact },
            ]}
          />
        </Column>
        <Column title={t.footer.customerService}>
          <LinkList
            links={[
              { href: `/${locale}/returns`, label: t.nav.returns },
              { href: `/${locale}/faq`, label: t.nav.faq },
              { href: `/${locale}/support`, label: t.nav.support },
            ]}
          />
        </Column>
        <Column title={t.footer.shoppingGuide}>{soon}</Column>
      </nav>
      <div className="mx-auto flex max-w-6xl flex-col gap-4 border-t border-border px-4 py-6 text-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {(social.instagramUrl || social.whatsappUrl) && (
            <ul aria-label={t.footer.social} className="flex gap-4">
              {social.instagramUrl && (
                <li>
                  <a href={social.instagramUrl} rel="noopener noreferrer" className={linkClass}>
                    {t.footer.instagram}
                  </a>
                </li>
              )}
              {social.whatsappUrl && (
                <li>
                  <a href={social.whatsappUrl} rel="noopener noreferrer" className={linkClass}>
                    {t.footer.whatsapp}
                  </a>
                </li>
              )}
            </ul>
          )}
          {trust.length > 0 && (
            <ul aria-label={t.footer.trust} className="flex gap-4">
              {trust.map((b) => (
                <li key={b.id}>
                  {b.href ? (
                    <a href={b.href} rel="noopener noreferrer" className={linkClass}>
                      {b.label[locale]}
                    </a>
                  ) : (
                    b.label[locale]
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
        <p className="text-muted-foreground">
          © {year} {siteConfig.name}. {t.footer.rights}
        </p>
      </div>
    </footer>
  );
}
