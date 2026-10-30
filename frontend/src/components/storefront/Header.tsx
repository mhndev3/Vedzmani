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
    { href: `/${locale}/products`, label: "همه محصولات" },
    { href: `/${locale}/about`, label: t.nav.about },
    { href: `/${locale}/faq`, label: t.nav.faq },
    { href: `/${locale}/support`, label: t.nav.support },
  ];
}

export function Header({ locale, t }: { locale: Locale; t: Dictionary }) {
  const [visible, setVisible] = useState(true);
  const items = navItems(locale, t);

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
          categories={categories.map((category) => ({
            href: `/${locale}/products?category=${encodeURIComponent(category.slug)}`,
            label: category.name,
          }))}
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
        <nav aria-label={t.a11y.mainNav} className="hidden items-center gap-5 text-sm md:flex">
          {items.map((item) => (
            <Link key={item.href} href={item.href} className="rounded py-2 text-muted-foreground transition-colors hover:text-foreground">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ms-auto flex items-center gap-1">
          <SearchButton locale={locale} />
          <CartButton locale={locale} />
          <ThemeToggle label={t.a11y.toggleTheme} />
        </div>
      </div>
    </header>
  );
}
