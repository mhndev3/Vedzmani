import "server-only";
import { emptyState, getProducts, type ProductCardData } from "./catalog";
import { apiGet } from "./api";

export type HomepageCategoryImage = { url: string; thumbnail_url?: string; alt_text?: string; width?: number; height?: number };
export type HomepageCategory = { id?: number; name: string; slug: string; image: HomepageCategoryImage | null };
export type HomepageSection = {
  id: number; position: number; title: string; eyebrow: string; section_type: "categories" | "products" | "newest_products";
  show_view_all: boolean; view_all_url: string;
  category_ids: number[]; product_ids: number[];
  categories: HomepageCategory[]; products: ProductCardData[];
};
export type HomepageBanner = {
  id: number; title: string; subtitle: string; alt_text: string;
  desktop_image: string; mobile_image: string | null; cta_label: string; cta_url: string;
};
export type HomepageContent = {
  banners: HomepageBanner[];
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
  let banners: HomepageBanner[] = [];
  try {
    const bannerResponse = await apiGet<{ banners: HomepageBanner[] }>("/api/catalog/homepage-banners/", {
      cache: "no-store",
    });
    banners = bannerResponse.banners;
  } catch {
    // Keep the static brand hero if banner configuration is unavailable.
  }

  try {
    const configured = await apiGet<{ sections: HomepageSection[] }>("/api/catalog/homepage-sections/", {
      cache: "no-store",
    });
    if (configured.sections.length > 0) {
      return { banners, categories: [], newestProducts: [], sections: configured.sections };
    }
  } catch {
    // Keep the existing homepage available if the new endpoint is temporarily unavailable.
  }

  try {
    let catalogCategories: HomepageCategory[] = [];
    try {
      const filters = await apiGet<{ categories: HomepageCategory[] }>("/api/catalog/filters/", {
        cache: "force-cache",
        next: { revalidate: 30 },
      });
      catalogCategories = filters.categories;
    } catch {
      // Category images are optional; keep the product-image fallback below.
    }
    const page = await getProducts(emptyState, { cache: "force-cache", next: { revalidate: 30 } });
    const products = page.results;
    const categoryBySlug = new Map(catalogCategories.map((category) => [category.slug, category]));
    return {
      banners,
      sections: [],
      categories: HOME_CATEGORIES.map((category) => ({
        ...category,
        image: categoryBySlug.get(category.slug)?.image ?? products.find((product) => product.category.slug === category.slug)?.image ?? null,
      })),
      newestProducts: products.slice(0, 7),
    };
  } catch {
    return {
      banners,
      sections: [],
      categories: HOME_CATEGORIES.map((category) => ({ ...category, image: null })),
      newestProducts: [],
    };
  }
}
