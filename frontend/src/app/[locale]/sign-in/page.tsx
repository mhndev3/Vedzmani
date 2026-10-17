import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SignInForm } from "@/components/auth/SignInForm";
import { isLocale } from "@/i18n/config";
import { getAuthDictionary } from "@/i18n/dictionaries/auth";
import { safeRedirectPath } from "@/lib/auth/redirect";

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ next?: string | string[] }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  // Personal flow: never indexed.
  return { title: getAuthDictionary(locale).title, robots: { index: false, follow: false } };
}

/**
 * Sign-in shell. `?next=` is sanitized here (same-origin, locale-prefixed paths only); the form runs in the
 * browser against Django's OTP API and the session cookie Django sets.
 */
export default async function SignInPage({ params, searchParams }: Props) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const { next } = await searchParams;
  const t = getAuthDictionary(locale);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">{t.title}</h1>
      <p className="mt-2 text-muted-foreground">{t.intro}</p>
      <SignInForm locale={locale} t={t} redirectTo={safeRedirectPath(next, locale)} />
    </div>
  );
}
