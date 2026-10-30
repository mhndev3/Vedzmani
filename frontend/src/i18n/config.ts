/** The storefront is Persian-only. */
export const locales = ["fa"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "fa";
export const localeMeta: Record<Locale, { dir: "rtl"; nativeName: string; ogLocale: string; numberLocale: string }> = {
  fa: { dir: "rtl", nativeName: "فارسی", ogLocale: "fa_IR", numberLocale: "fa-IR" },
};
export function isLocale(value: unknown): value is Locale {
  return value === "fa";
}
