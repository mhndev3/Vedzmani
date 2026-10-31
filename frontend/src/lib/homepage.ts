import "server-only";
import { emptyState, getProducts, type CatalogImage, type ProductCardData } from "./catalog";

export type HomepageCategory = {
  name: string;
  slug: string;
  image: CatalogImage | null;
};

export type HomepageContent = {
  categories: HomepageCategory[];
  newestProducts: ProductCardData[];
};

const HOME_CATEGORIES = [
  { name: "دورس", slug: "sweatshirts" },
  { name: "بافت", slug: "knitwear" },
  { name: "شلوار جین", slug: "jeans" },
  { name: "جکت چرم", slug: "leather-jackets" },
  { name: "هودی", slug: "hoodies" },
] as const;

/**
 * Fetch the newest catalog page once and derive both homepage sections from it.
 * The API's default ordering is newest-first; one request avoids five category
 * round-trips and keeps the homepage data path small.
 */
export async function getHomepageContent(): Promise<HomepageContent> {
  try {
    const page = await getProducts(emptyState);
    const products = page.results;
    return {
      categories: HOME_CATEGORIES.map((category) => ({
        ...category,
        image: products.find((product) => product.category.slug === category.slug)?.image ?? null,
      })),
      newestProducts: products.slice(0, 7),
    };
  } catch {
    return {
      categories: HOME_CATEGORIES.map((category) => ({ ...category, image: null })),
      newestProducts: [],
    };
  }
}
