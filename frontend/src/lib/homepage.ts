import "server-only";
import { emptyState, getProducts, type CatalogImage, type ProductCardData } from "./catalog";
import { apiGet } from "./api";

export type HomepageCategory = { name: string; slug: string; image: CatalogImage | null };
export type HomepageSection = {
  id: number; title: string; eyebrow: string; section_type: "categories" | "products" | "newest_products";
  show_view_all: boolean; view_all_url: string;
  categories: HomepageCategory[]; products: ProductCardData[];
};
export type HomepageContent = {
  categories: HomepageCategory[];
  newestProducts: ProductCardData[];
  sections: HomepageSection[];
};

const HOME_CATEGORIES = [
  { name: "دورس", slug: "sweatshirts" },
  { name: "بافت", slug: "knitwear" },
  { name: "شلوار", slug: "jeans" },
  { name: "هودی", slug: "hoodies" },
  { name: "جکت چرم", slug: "leather-jackets" },
] as const;

/** Prefer published admin configuration; retain the original storefront when no section is published. */
export async function getHomepageContent(): Promise<HomepageContent> {
  try {
    const configured = await apiGet<{ sections: HomepageSection[] }>("/api/catalog/homepage-sections/", {
      cache: "no-store",
    });
    if (configured.sections.length > 0) {
      return { categories: [], newestProducts: [], sections: configured.sections };
    }
  } catch {
    // Keep the existing homepage available if the new endpoint is temporarily unavailable.
  }

  try {
    const page = await getProducts(emptyState, { cache: "force-cache", next: { revalidate: 30 } });
    const products = page.results;
    return {
      sections: [],
      categories: HOME_CATEGORIES.map((category) => ({
        ...category,
        image: products.find((product) => product.category.slug === category.slug)?.image ?? null,
      })),
      newestProducts: products.slice(0, 7),
    };
  } catch {
    return {
      sections: [],
      categories: HOME_CATEGORIES.map((category) => ({ ...category, image: null })),
      newestProducts: [],
    };
  }
}
