"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { defaultLocale, isLocale } from "@/i18n/config";
import { productStates } from "@/i18n/dictionaries/product-states";

/**
 * Shown when the product page calls notFound() (Django answered 404), so the response keeps its
 * 404 status. not-found.tsx gets no params, so the locale is read from the URL's first segment.
 */
export default function ProductNotFound() {
  const segment = usePathname().split("/")[1];
  const locale = isLocale(segment) ? segment : defaultLocale;
  const t = productStates[locale];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="rounded-lg border border-border bg-muted p-8 text-center">
        <h1 className="font-medium">{t.title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t.text}</p>
        <Link
          href={`/${locale}/products`}
          className="mt-4 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          {t.back}
        </Link>
      </div>
    </div>
  );
}
