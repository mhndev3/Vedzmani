"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { MobileNav } from "./MobileNav";
import { ThemeToggle } from "./ThemeToggle";
import { SearchButton } from "./SearchButton";
import { MobileSearchPanel } from "./MobileSearchPanel";
import { CartButton } from "./CartButton";

const categories = [
  { name: "دورس", slug: "sweatshirts" },
  { name: "پیراهن", slug: "shirts" },
  { name: "تی شرت", slug: "t-shirts" },
  { name: "هودی", slug: "hoodies" },
  { name: "کاپشن", slug: "coats" },
  { name: "جکت", slug: "jackets" },
  { name: "شلوار جین", slug: "jeans" },
  { name: "شلوار پارچه ای", slug: "trousers" },
  { name: "شلوار جاگر", slug: "joggers" },
  { name: "کتونی", slug: "sneakers" },
  { name: "اکسسوری", slug: "accessories" },
  { name: "بافت", slug: "knitwear" },
  { name: "جکت چرم", slug: "leather-jackets" },
];

export function navItems(locale: Locale, t: Dictionary) {
  return [
    { href: "/" + locale + "/products", label: "همه محصولات" },
    { href: "/" + locale + "/about", label: t.nav.about },
    { href: "/" + locale + "/faq", label: t.nav.faq },
    { href: "/" + locale + "/support", label: t.nav.support },
  ];
}

export function Header({ locale, t }: { locale: Locale; t: Dictionary }) {
  const [visible, setVisible] = useState(true);
  const [searchOpenedOnPath, setSearchOpenedOnPath] = useState<string | null>(null);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const pathname = usePathname();
  const searchExpanded = searchOpenedOnPath === pathname;
  const hideTimer = useRef<number | undefined>(undefined);
  const items = navItems(locale, t);
  const categoryItems = categories.map((category) => ({
    href: "/" + locale + "/categories/" + encodeURIComponent(category.slug),
    label: category.name,
  }));

  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      if (searchExpanded || mobileSearchOpen) {
        setVisible(true);
        return;
      }
      if (!frame) {
        frame = window.requestAnimationFrame(() => {
          setVisible((current) => (current ? false : current));
          frame = 0;
        });
      }
      if (hideTimer.current !== undefined) window.clearTimeout(hideTimer.current);
      hideTimer.current = window.setTimeout(() => setVisible(true), 120);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
      if (hideTimer.current !== undefined) window.clearTimeout(hideTimer.current);
    };
  }, [searchExpanded, mobileSearchOpen]);

  return (
    <header
      aria-hidden={!visible}
      inert={!visible}
      className={"sticky top-0 z-40 transition-transform duration-150 motion-reduce:transition-none " + (visible ? "translate-y-0" : "-translate-y-full")}
    >
      <div className={"relative flex flex-col border border-border bg-background/95 shadow-sm transition-[height,width,max-width,border-radius,margin,padding] duration-200 md:flex-row md:items-center " + (searchExpanded ? "my-0 h-20 w-full max-w-none rounded-b-2xl rounded-t-none px-3 sm:px-5" : mobileSearchOpen ? "my-0 h-auto min-h-16 w-full max-w-none rounded-2xl px-0 md:mx-auto md:my-2 md:h-16 md:max-w-6xl md:rounded-full md:px-3" : "mx-auto my-2 h-16 max-w-6xl rounded-full px-3 sm:px-4")}>
        <div className="flex h-16 w-full shrink-0 items-center gap-3 px-3 sm:px-4 md:h-full md:px-0">
        <MobileNav
          items={items}
          categories={categoryItems}
          labels={{
            open: t.a11y.openMenu,
            close: t.a11y.closeMenu,
            title: t.a11y.menuTitle,
            categories: "دسته‌بندی‌ها",
          }}
        />
        <Link href={"/" + locale} prefetch={false} aria-label="صفحه اصلی ودزمانی" className="inline-flex size-12 shrink-0 items-center justify-center">
          <Image
            src="/images/vedzmani-mark.svg"
            alt="نشان گرد ودزمانی"
            width={48}
            height={48}
            priority
            sizes="48px"
            className="size-12 rounded-full object-cover invert dark:invert-0"
          />
        </Link>
        <nav aria-label={t.a11y.mainNav} className="hidden flex-1 items-center justify-center gap-3 text-sm md:flex">
          <Link href={items[0].href} prefetch={false} className="rounded-full px-3 py-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
            {items[0].label}
          </Link>
          <details className="group relative">
            <summary className="flex cursor-pointer list-none items-center gap-1 rounded py-2 text-muted-foreground transition-colors hover:text-foreground [&::-webkit-details-marker]:hidden">
              دسته‌بندی‌ها
              <svg aria-hidden="true" viewBox="0 0 16 16" className="size-3.5 transition-transform duration-150 ease-out group-open:rotate-90 motion-reduce:transition-none" fill="none">
                <path d="M6 3.5 10.5 8 6 12.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </summary>
            <div className="absolute end-0 top-full z-50 mt-2 grid min-w-64 grid-cols-2 gap-1 rounded-xl border border-border bg-background p-2 shadow-xl">
              {categories.map((category) => (
                <Link key={category.slug} href={"/" + locale + "/categories/" + encodeURIComponent(category.slug)} prefetch={false} className="rounded-lg px-3 py-2.5 text-sm hover:bg-muted">{category.name}</Link>
              ))}
            </div>
          </details>
          {items.slice(1).map((item) => (
            <Link key={item.href} href={item.href} prefetch={false} className="rounded py-2 text-muted-foreground transition-colors hover:text-foreground">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className={"ms-auto flex items-center gap-1 " + (searchExpanded ? "min-w-0 flex-1" : "shrink-0")}>
          <div className="hidden md:block">
            <SearchButton locale={locale} expanded={searchExpanded} onExpandedChange={(value) => setSearchOpenedOnPath(value ? pathname : null)} />
          </div>
          <button type="button" onClick={() => setMobileSearchOpen((value) => !value)} aria-label="جستجوی محصولات" aria-expanded={mobileSearchOpen} className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg hover:bg-muted md:hidden">
            <svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4.5 4.5" /></svg>
          </button>
          <CartButton locale={locale} />
          <Link href={"/" + locale + "/profile"} prefetch={false} aria-label="حساب کاربری" title="حساب کاربری" className="inline-flex size-9 items-center justify-center rounded-lg hover:bg-muted">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="3.5" /><path d="M5 21a7 7 0 0 1 14 0" /></svg>
          </Link>
          <ThemeToggle label={t.a11y.toggleTheme} />
        </div>
        <MobileSearchPanel locale={locale} open={mobileSearchOpen} onClose={() => setMobileSearchOpen(false)} />
      </div>
    </header>
  );
}
