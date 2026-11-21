import { NextResponse } from "next/server";

export const dynamic = "force-static";

const SITE_ORIGIN = (process.env.NEXT_PUBLIC_SITE_URL || "https://vedzmani.ir").replace(/\/$/, "");

export function GET() {
  const body = [
    "User-agent: *",
    "Allow: /",
    "Disallow: /api/",
    "Disallow: /_next/",
    "Disallow: /fa/cart",
    "Disallow: /fa/profile",
    "Disallow: /fa/admin-panel",
    "",
    `Sitemap: ${SITE_ORIGIN}/sitemap.xml`,
    "",
  ].join("\n");

  return new NextResponse(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
