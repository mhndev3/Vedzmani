import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CartView } from "@/components/storefront/cart/CartView";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale)
    ? { title: getDictionary(locale).cart.title, robots: { index: false } }
    : {};
}

/** The cart is per-customer and loaded in the browser through the session cookie. */
export default async function CartPage({ params }: Props) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <CartView locale={locale} t={getDictionary(locale).cart} />;
}
