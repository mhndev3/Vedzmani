import "server-only";

/**
 * Homepage data boundary: Homepage -> sections (data) -> presentation.
 *
 * The backend currently exposes only /api/catalog/products/<slug>/ (no list
 * endpoints), so there is no real data for these sections yet. Items stay
 * empty and the UI shows an honest empty state, no fake products, prices or
 * discounts. When Agent 6 / Agent 8 expose list or homepage-config
 * endpoints, only this function changes.
 */
export type HomepageItem = { id: string; title: string; href: string };

export type HomepageSectionId =
  | "categories"
  | "featuredProducts"
  | "collections"
  | "promotions";

export type HomepageSection = { id: HomepageSectionId; items: HomepageItem[] };

const SECTION_ORDER: HomepageSectionId[] = [
  "categories",
  "featuredProducts",
  "collections",
  "promotions",
];

export async function getHomepageSections(): Promise<HomepageSection[]> {
  return SECTION_ORDER.map((id) => ({ id, items: [] }));
}
