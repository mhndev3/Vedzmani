import type { Locale } from "@/i18n/config";
import { localeMeta } from "@/i18n/config";

/**
 * Presentation helpers with no server-only dependency, so Server and Client
 * Components can share them (catalog.ts re-exports these for existing callers).
 */

/** Prices are whole currency units; the currency itself is still undecided, so none is shown. */
export function formatPrice(value: string | number, locale: Locale): string {
  return new Intl.NumberFormat(localeMeta[locale].numberLocale, {
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => String(values[k] ?? ""));
}
