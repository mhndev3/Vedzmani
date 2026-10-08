/**
 * Locale architecture: the locale is the first URL segment (/fa/..., /en/...).
 * `lang` and `dir` are derived from it once, in the root layout, so no
 * component needs its own RTL/LTR handling (use CSS logical properties).
 * To add a language: add it here, add a dictionary, done.
 */
export const locales = ["fa", "en"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "fa";

export const localeMeta: Record<
  Locale,
  { dir: "rtl" | "ltr"; nativeName: string; ogLocale: string; numberLocale: string }
> = {
  fa: { dir: "rtl", nativeName: "فارسی", ogLocale: "fa_IR", numberLocale: "fa-IR" },
  en: { dir: "ltr", nativeName: "English", ogLocale: "en_US", numberLocale: "en-US" },
};

export const LOCALE_COOKIE = "NEXT_LOCALE";

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (locales as readonly string[]).includes(value);
}

/** With exactly two languages the switcher toggles; extend here for more. */
export function otherLocale(locale: Locale): Locale {
  return locale === "fa" ? "en" : "fa";
}
