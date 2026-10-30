import type { Locale } from "@/i18n/config";

export const STORE_CATEGORIES = [
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
] as const;

export function categoryHref(locale: Locale, slug: string): string {
  return `/${locale}/products?category=${encodeURIComponent(slug)}`;
}

export function categoryName(slug: string): string {
  return STORE_CATEGORIES.find((category) => category.slug === slug)?.name ?? slug;
}
