import Link from "next/link";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { siteConfig } from "@/lib/site-config";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { MobileNav } from "./MobileNav";
import { ThemeToggle } from "./ThemeToggle";

export function navItems(locale: Locale, t: Dictionary) {
  return [
    { href: `/${locale}/about`, label: t.nav.about },
    { href: `/${locale}/contact`, label: t.nav.contact },
    { href: `/${locale}/returns`, label: t.nav.returns },
    { href: `/${locale}/faq`, label: t.nav.faq },
    { href: `/${locale}/support`, label: t.nav.support },
    { href: `/${locale}/profile`, label: t.nav.profile },
  ];
}

/** Server Component. Sticky via CSS only (no scroll listener, no JS). */
export function Header({ locale, t }: { locale: Locale; t: Dictionary }) {
  const items = navItems(locale, t);
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-2 px-4">
        <MobileNav
          items={[{ href: `/${locale}`, label: t.nav.home }, ...items]}
          labels={{ open: t.a11y.openMenu, close: t.a11y.closeMenu, title: t.a11y.menuTitle }}
        />
        <Link
          href={`/${locale}`}
          className="flex items-center gap-2 rounded-lg px-1 text-lg font-semibold tracking-tight"
        >
          <span
            aria-hidden="true"
            className="inline-flex size-8 items-center justify-center rounded-lg bg-primary text-sm text-primary-foreground"
          >
            V
          </span>
          {siteConfig.name}
        </Link>
        <nav aria-label={t.a11y.mainNav} className="ms-6 hidden lg:block">
          <ul className="flex items-center gap-1">
            {items.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="rounded-lg px-3 py-2 text-sm hover:bg-muted">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="ms-auto flex items-center gap-1">
          <LanguageSwitcher locale={locale} label={t.a11y.switchLanguage} />
          <ThemeToggle label={t.a11y.toggleTheme} />
        </div>
      </div>
    </header>
  );
}
