import type { Locale } from "@/i18n/config";
import { localeMeta } from "@/i18n/config";

/**
 * Presentation helpers with no server-only dependency, so Server and Client
 * Components can share them (catalog.ts re-exports these for existing callers).
 */

/** Format a whole number without losing precision for large server-owned Decimal strings. */
export function formatPrice(value: string | number, locale: Locale): string {
  const raw = String(value).trim();
  const formattedValue = /^-?\\d+$/.test(raw) ? BigInt(raw) : Number(value);
  return new Intl.NumberFormat(localeMeta[locale].numberLocale, {
    maximumFractionDigits: 0,
  }).format(formattedValue);
}

/** All storefront and checkout prices are denominated in Iranian Toman. */
export function formatCurrency(value: string | number, locale: Locale): string {
  return `${formatPrice(value, locale)} تومان`;
}

export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => String(values[k] ?? ""));
}
