import { NextResponse, type NextRequest } from "next/server";
import { defaultLocale, isLocale } from "@/i18n/config";

/** All storefront requests use the Persian locale; legacy English URLs are redirected. */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const url = request.nextUrl.clone();

  if (pathname === "/en" || pathname.startsWith("/en/")) {
    url.pathname = `/fa${pathname.slice(3)}`;
    return NextResponse.redirect(url, 308);
  }
  if (isLocale(pathname.split("/")[1])) return NextResponse.next();

  url.pathname = `/${defaultLocale}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url, 308);
}

export const config = {
  matcher: ["/((?!api|_next|healthz|.*\\..*).*)"],
};
