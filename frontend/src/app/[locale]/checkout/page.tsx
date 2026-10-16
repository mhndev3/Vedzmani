import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CheckoutForm } from "@/components/checkout/CheckoutForm";
import { isLocale } from "@/i18n/config";
import { getCheckoutDictionary } from "@/i18n/dictionaries/checkout";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  // Personal, per-customer page: never indexed, even once the site is.
  return { title: getCheckoutDictionary(locale).title, robots: { index: false, follow: false } };
}

/**
 * Checkout shell. All data (session, cart, order) is loaded in the browser from
 * the Django API with the customer's own session cookie; nothing personal is
 * rendered or cached on the server.
 */
export default async function CheckoutPage({ params }: Props) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getCheckoutDictionary(locale);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-3xl font-semibold tracking-tight">{t.title}</h1>
      <p className="mt-2 text-muted-foreground">{t.intro}</p>
      <CheckoutForm locale={locale} t={t} />
    </div>
  );
}
