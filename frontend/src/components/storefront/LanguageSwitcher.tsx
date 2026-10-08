"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LOCALE_COOKIE, localeMeta, otherLocale, type Locale } from "@/i18n/config";
import { GlobeIcon } from "./icons";

/** A real link to the same route in the other locale (URL and app locale change together). */
export function LanguageSwitcher({ locale, label }: { locale: Locale; label: string }) {
  const pathname = usePathname();
  const target = otherLocale(locale);
  const rest = pathname.replace(/^\/[^/]+/, "");
  const href = `/${target}${rest}`;

  return (
    <Link
      href={href}
      prefetch={false}
      hrefLang={target}
      lang={target}
      aria-label={label}
      onClick={() => {
        document.cookie = `${LOCALE_COOKIE}=${target}; path=/; max-age=31536000; samesite=lax`;
      }}
      className="inline-flex h-10 items-center gap-1.5 rounded-lg px-2.5 text-sm hover:bg-muted"
    >
      <GlobeIcon />
      <span>{localeMeta[target].nativeName}</span>
    </Link>
  );
}
