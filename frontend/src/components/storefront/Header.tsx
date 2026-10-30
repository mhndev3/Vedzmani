"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { MobileNav } from "./MobileNav";
import { ThemeToggle } from "./ThemeToggle";
import { SearchButton } from "./SearchButton";
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
  { name: "جاگر", slug: "joggers" },
  { name: "کتونی", slug: "sneakers" },
  { name: "اکسسوری", slug: "accessories" },
];

export function navItems(locale: Locale, t: Dictionary) {
  return [
    { href: `/${locale}/products`, label: "محصولات" },
    { href: `/${locale}/about`, label: t.nav.about },
    { href: `/${locale}/faq`, label: t.nav.faq },
    { href: `/${locale}/support`, label: t.nav.support },
  ];
}

export function Header({ locale, t }: { locale: Locale; t: Dictionary }) {
  const [visible, setVisible] = useState(true);
  const items = navItems(locale, t);
  const categoryItems = categories.map((category) => ({
    href: `/${locale}/categories/${encodeURIComponent(category.slug)}`,
    label: category.name,
  }));

  useEffect(() => {
    let timer: number | undefined;
    const onScroll = () => {
      setVisible(false);
      if (timer !== undefined) window.clearTimeout(timer);
      timer = window.setTimeout(() => setVisible(true), 220);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  return (
    <header
      aria-hidden={!visible}
      inert={!visible}
      className={`sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur transition-transform duration-200 motion-reduce:transition-none ${visible ? "translate-y-0" : "-translate-y-full"}`}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4">
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
        <Link href={`/${locale}`} aria-label="صفحه اصلی ودزمانی" className="inline-flex shrink-0 items-center rounded-lg">
          <Image src="/favicon.ico" alt="نشان ودزمانی" width={36} height={36} unoptimized priority />
        </Link>
        <nav aria-label={t.a11y.mainNav} className="hidden flex-1 items-center justify-center gap-5 text-sm md:flex">
          <Link href={items[0].href} className="rounded py-2 text-muted-foreground transition-colors hover:text-foreground">
            {items[0].label}
          </Link>
          <details className="group relative">
            <summary className="flex cursor-pointer list-none items-center gap-1 rounded py-2 text-muted-foreground transition-colors hover:text-foreground [&::-webkit-details-marker]:hidden">
              دسته‌بندی‌ها
              <svg
                aria-hidden="true"
                viewBox="0 0 16 16"
                className="size-3.5 transition-transform duration-200 ease-out group-open:rotate-90 motion-reduce:transition-none"
                fill="none"
              >
                <path d="M6 3.5 10.5 8 6 12.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </summary>
            <div className="absolute end-0 top-full z-50 mt-2 grid min-w-64 grid-cols-2 gap-1 rounded-xl border border-border bg-background p-2 shadow-xl">
              {categories.map((category) => (
                <Link key={category.slug} href={'/' + locale + '/categories/' + encodeURIComponent(category.slug)} className="rounded-lg px-3 py-2.5 text-sm hover:bg-muted">{category.name}</Link>
              ))}
            </div>
          </details>
          {items.slice(1).map((item) => (
            <Link key={item.href} href={item.href} className="rounded py-2 text-muted-foreground transition-colors hover:text-foreground">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ms-auto flex shrink-0 items-center gap-1">
          <SearchButton locale={locale} />
          <CartButton locale={locale} />
          <Link href={'/' + locale + '/profile'} aria-label="حساب کاربری" title="حساب کاربری" className="inline-flex size-9 items-center justify-center rounded-lg hover:bg-muted">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="3.5" /><path d="M5 21a7 7 0 0 1 14 0" /></svg>
          </Link>
          <ThemeToggle label={t.a11y.toggleTheme} />
        </div>
      </div>
    </header>
  );
}
