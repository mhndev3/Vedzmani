import type { Locale } from "@/i18n/config";

type Localized = Record<Locale, string>;

/**
 * Store-level facts that are NOT known yet. Nothing here is invented:
 * empty/null values render nothing in the UI. Fill in real values (or
 * replace this module with an API-backed source later) without touching
 * any component.
 */
export const siteConfig = {
  name: "Vedzmani",
  social: {
    instagramUrl: null as string | null,
    whatsappUrl: null as string | null,
  },
  /** Footer benefit row, e.g. { id: "x", label: { fa: "...", en: "..." } }. */
  features: [] as { id: string; label: Localized }[],
  /** Licenses / trust badges, only real, verified entries. */
  trust: [] as { id: string; label: Localized; href?: string }[],
};
