import type { Locale } from "@/i18n/config";

/**
 * Copy for the product "not found" page. Own small module (like auth.ts and checkout.ts) because
 * Next.js renders not-found.tsx without params, so it is a Client Component that derives the locale
 * from the URL; importing the full server-only dictionaries there would ship them to the browser.
 * Both locales must define every key.
 */
const en = {
  title: "Product not found",
  text: "This product does not exist or is no longer available.",
  back: "Back to products",
};

const fa: typeof en = {
  title: "محصول پیدا نشد",
  text: "این محصول وجود ندارد یا دیگر در دسترس نیست.",
  back: "بازگشت به محصولات",
};

export const productStates: Record<Locale, typeof en> = { fa, en };
