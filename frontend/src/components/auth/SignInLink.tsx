import Link from "next/link";
import type { Locale } from "@/i18n/config";
import { getAuthDictionary } from "@/i18n/dictionaries/auth";
import { signInHref } from "@/lib/auth/redirect";

/** Link to the sign-in page that brings the customer back to `next` (a locale-prefixed path). Usable in Server and Client Components. */
export function SignInLink({
  locale,
  next,
  className = "inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground",
}: {
  locale: Locale;
  next: string;
  className?: string;
}) {
  return (
    <Link href={signInHref(locale, next)} className={className}>
      {getAuthDictionary(locale).signInLink}
    </Link>
  );
}
