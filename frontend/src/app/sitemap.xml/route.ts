import { NextResponse } from "next/server";
import { apiGet } from "@/lib/api";
import type { FilterOptions, Paginated, ProductCardData } from "@/lib/catalog";

export const revalidate = 3600;

const SITE_ORIGIN = (process.env.NEXT_PUBLIC_SITE_URL || "https://vedzmani.ir").replace(/\/$/, "");
const LOCALE = "fa";
const PAGE_SIZE = 60;

function xmlEscape(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}

function urlEntry(path: string): string {
  return `  <url><loc>${xmlEscape(SITE_ORIGIN + path)}</loc></url>`;
}

async function getPublishedProductSlugs(): Promise<string[]> {
  const slugs = new Set<string>();
  let page = 1;
  let pageCount = 1;

  while (page <= pageCount && page <= 500) {
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    const result = await apiGet<Paginated<ProductCardData>>(
      `/api/catalog/variant-products/?${query.toString()}`,
      { cache: "force-cache", next: { revalidate: 3600 } },
    );
    for (const product of result.results) {
      if (product.slug) slugs.add(product.slug);
    }
    pageCount = Math.ceil(result.count / PAGE_SIZE);
    page += 1;
  }

  return [...slugs];
}

export async function GET() {
  try {
    const [filters, productSlugs] = await Promise.all([
      apiGet<FilterOptions>("/api/catalog/filters/", {
        cache: "force-cache",
        next: { revalidate: 3600 },
      }),
      getPublishedProductSlugs(),
    ]);

    const staticPaths = [
      `/${LOCALE}`,
      `/${LOCALE}/products`,
      `/${LOCALE}/about`,
      `/${LOCALE}/faq`,
      `/${LOCALE}/support`,
    ];
    const categoryPaths = filters.categories.map((category) =>
      `/${LOCALE}/categories/${encodeURIComponent(category.slug)}`,
    );
    const productPaths = productSlugs.map((slug) =>
      `/${LOCALE}/products/${encodeURIComponent(slug)}`,
    );
    const entries = [...new Set([...staticPaths, ...categoryPaths, ...productPaths])].map(urlEntry);
    const xml = [
      '<?xml version="1.0" encoding="UTF-8"?>',
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
      ...entries,
      '</urlset>',
      '',
    ].join("\n");

    return new NextResponse(xml, {
      headers: {
        "Content-Type": "application/xml; charset=utf-8",
        "Cache-Control": "public, max-age=0, s-maxage=3600, stale-while-revalidate=86400",
      },
    });
  } catch {
    return new NextResponse("Sitemap temporarily unavailable", {
      status: 503,
      headers: { "Cache-Control": "no-store", "Retry-After": "300" },
    });
  }
}
