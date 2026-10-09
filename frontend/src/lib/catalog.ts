import "server-only";
import { cache } from "react";
import { apiGet, ApiError } from "./api";
import type { Locale } from "@/i18n/config";
import { localeMeta } from "@/i18n/config";

/**
 * Catalog data boundary. Django owns filtering, search, sorting, pagination
 * and stock truth; this module only (1) normalizes URL state into the query
 * the backend documents in backend/CATALOG.md and (2) types the responses.
 */

export const PAGE_SIZE = 24;
export const SORTS = ["newest", "price_asc", "price_desc", "name_asc", "name_desc"] as const;
export type Sort = (typeof SORTS)[number];
export const DEFAULT_SORT: Sort = "newest";

const MULTI_KEYS = ["category", "collection", "color", "size"] as const;
type MultiKey = (typeof MULTI_KEYS)[number];

const SLUG_RE = /^[-a-zA-Z0-9_]+$/;
const MAX_VALUES = 10;

export type CatalogState = {
  search: string;
  category: string[];
  collection: string[];
  color: string[];
  size: string[];
  minPrice: string;
  maxPrice: string;
  inStock: boolean;
  sort: Sort;
  page: number;
};

type RawParams = Record<string, string | string[] | undefined>;

function all(raw: RawParams, key: string): string[] {
  const v = raw[key];
  return v === undefined ? [] : Array.isArray(v) ? v : [v];
}

function multi(raw: RawParams, key: MultiKey): string[] {
  const values = all(raw, key)
    .flatMap((v) => v.split(","))
    .map((v) => v.trim())
    .filter((v) => SLUG_RE.test(v));
  return [...new Set(values)].slice(0, MAX_VALUES);
}

function wholeNumber(raw: RawParams, key: string): string {
  const v = all(raw, key)[0]?.trim() ?? "";
  return /^\d{1,14}$/.test(v) ? String(Number(v)) : "";
}

/** Presentation-level sanitising of the URL only; the backend still validates everything. */
export function parseCatalogState(raw: RawParams): CatalogState {
  const sort = all(raw, "sort")[0];
  const page = Number(all(raw, "page")[0]);
  let minPrice = wholeNumber(raw, "min_price");
  let maxPrice = wholeNumber(raw, "max_price");
  if (minPrice && maxPrice && Number(minPrice) > Number(maxPrice)) {
    [minPrice, maxPrice] = [maxPrice, minPrice];
  }
  return {
    search: (all(raw, "search")[0] ?? "").trim().slice(0, 100),
    category: multi(raw, "category"),
    collection: multi(raw, "collection"),
    color: multi(raw, "color"),
    size: multi(raw, "size"),
    minPrice,
    maxPrice,
    inStock: all(raw, "in_stock")[0] === "true",
    sort: (SORTS as readonly string[]).includes(sort ?? "") ? (sort as Sort) : DEFAULT_SORT,
    page: Number.isInteger(page) && page > 1 ? page : 1,
  };
}

/** Canonical, compact URL query for a state (defaults omitted). */
export function stateToParams(state: CatalogState): URLSearchParams {
  const p = new URLSearchParams();
  if (state.search) p.set("search", state.search);
  for (const key of MULTI_KEYS) {
    if (state[key].length) p.set(key, state[key].join(","));
  }
  if (state.minPrice) p.set("min_price", state.minPrice);
  if (state.maxPrice) p.set("max_price", state.maxPrice);
  if (state.inStock) p.set("in_stock", "true");
  if (state.sort !== DEFAULT_SORT) p.set("sort", state.sort);
  if (state.page > 1) p.set("page", String(state.page));
  return p;
}

export function catalogHref(locale: Locale, state: CatalogState): string {
  const qs = stateToParams(state).toString();
  return `/${locale}/products${qs ? `?${qs}` : ""}`;
}

export const emptyState: CatalogState = {
  search: "",
  category: [],
  collection: [],
  color: [],
  size: [],
  minPrice: "",
  maxPrice: "",
  inStock: false,
  sort: DEFAULT_SORT,
  page: 1,
};

/** True when anything narrows the listing (page and sort do not count). */
export function hasActiveNarrowing(state: CatalogState): boolean {
  return (
    !!state.search ||
    MULTI_KEYS.some((k) => state[k].length > 0) ||
    !!state.minPrice ||
    !!state.maxPrice ||
    state.inStock
  );
}

export type CatalogImage = { url: string; alt_text: string; width: number; height: number };
export type Swatch = { name: string; slug: string; hex_color: string };

export type ProductCardData = {
  id: number;
  name: string;
  slug: string;
  price: string;
  sale_price: string | null;
  category: { name: string; slug: string };
  in_stock: boolean;
  image: CatalogImage | null;
  colors: Swatch[];
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type FilterOptions = {
  categories: { name: string; slug: string }[];
  collections: { name: string; slug: string }[];
  colors: Swatch[];
  sizes: { code: string; label: string }[];
};

export type ProductDetail = {
  id: number;
  name: string;
  slug: string;
  description: string;
  price: string;
  sale_price: string | null;
  category: { name: string; slug: string };
  colors: {
    id: number;
    name: string;
    slug: string;
    hex_color: string;
    images: {
      url: string;
      alt_text: string;
      position: number;
      is_primary: boolean;
      width: number;
      height: number;
    }[];
    sizes: { id: number; size: string; label: string; sku: string; in_stock: boolean }[];
  }[];
};

export function totalPages(count: number): number {
  return Math.max(1, Math.ceil(count / PAGE_SIZE));
}

export async function getProducts(state: CatalogState): Promise<Paginated<ProductCardData>> {
  const p = stateToParams(state);
  p.set("page_size", String(PAGE_SIZE));
  return apiGet<Paginated<ProductCardData>>(`/api/catalog/products/?${p.toString()}`);
}

/** Vocabulary changes rarely; a short revalidation window keeps this off the hot path. */
export const getFilterOptions = cache(async (): Promise<FilterOptions> => {
  return apiGet<FilterOptions>("/api/catalog/filters/", {
    cache: "force-cache",
    next: { revalidate: 60 },
  });
});

/** Returns null when the product does not exist (404); other failures throw. */
export const getProduct = cache(async (slug: string): Promise<ProductDetail | null> => {
  try {
    return await apiGet<ProductDetail>(`/api/catalog/products/${encodeURIComponent(slug)}/`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
});

/** Prices are whole currency units; the currency itself is still undecided, so none is shown. */
export function formatPrice(value: string | number, locale: Locale): string {
  return new Intl.NumberFormat(localeMeta[locale].numberLocale, {
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => String(values[k] ?? ""));
}
