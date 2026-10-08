import { NextResponse, type NextRequest } from "next/server";
import { LOCALE_COOKIE, defaultLocale, isLocale } from "@/i18n/config";

/**
 * Locale routing: every storefront URL carries its locale (/fa, /en).
 * Unprefixed paths are redirected to the user's last chosen locale
 * (cookie set by the language switcher) or to the default (Persian).
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (isLocale(pathname.split("/")[1])) return NextResponse.next();

  const cookie = request.cookies.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(cookie) ? cookie : defaultLocale;
  const url = request.nextUrl.clone();
  url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Skip API (served by Django via Nginx), Next internals, health and files.
  matcher: ["/((?!api|_next|healthz|.*\\..*).*)"],
};
