import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { ApiError } from "@/lib/api";
import {
  catalogHref,
  emptyState,
  fill,
  formatPrice,
  getFilterOptions,
  getProducts,
  hasActiveNarrowing,
  parseCatalogState,
  type FilterOptions,
  type Paginated,
  type ProductCardData,
} from "@/lib/catalog";
import { FilterDrawer } from "@/components/storefront/catalog/FilterDrawer";
import {
  FilterForm,
  Pagination,
  SearchForm,
  SortLinks,
} from "@/components/storefront/catalog/CatalogControls";
import { ProductCard } from "@/components/storefront/catalog/ProductCard";

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Pick<Props, "params">): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  return { title: getDictionary(locale).catalog.title };
}

export default async function ProductsPage({ params, searchParams }: Props) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  const state = parseCatalogState(await searchParams);

  // Both requests start together; the filter vocabulary is optional (the page works without it).
  const optionsPromise: Promise<FilterOptions | null> = getFilterOptions().catch(() => null);
  let data: Paginated<ProductCardData> | null = null;
  let pageOutOfRange = false;
  try {
    data = await getProducts(state);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404 && state.page > 1) pageOutOfRange = true;
  }
  if (pageOutOfRange) redirect(catalogHref(locale, { ...state, page: 1 }));
  const options = await optionsPromise;

  const narrowing = hasActiveNarrowing(state);
  const activeFilterCount =
    state.category.length +
    state.collection.length +
    state.color.length +
    state.size.length +
    (state.minPrice || state.maxPrice ? 1 : 0) +
    (state.inStock ? 1 : 0);
  const hasFilterOptions =
    !!options &&
    (options.categories.length > 0 ||
      options.collections.length > 0 ||
      options.colors.length > 0 ||
      options.sizes.length > 0);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t.catalog.title}</h1>

      <div className="mt-4">
        <SearchForm locale={locale} t={t} state={state} />
      </div>

      <div className={`mt-6 ${hasFilterOptions ? "lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:items-start lg:gap-8" : ""}`}>
        {hasFilterOptions && options && (
          <aside className="mb-6 lg:mb-0">
            <FilterDrawer
              title={t.catalog.filters}
              closeLabel={t.catalog.closeFilters}
              activeCount={activeFilterCount}
            >
              <FilterForm locale={locale} t={t} state={state} options={options} />
            </FilterDrawer>
          </aside>
        )}
        <section aria-labelledby="results-heading" className="min-w-0">
          {data ? (
            <>
              <div className="flex flex-wrap items-end justify-between gap-4">
                <h2 id="results-heading" className="text-sm text-muted-foreground" aria-live="polite">
                  {fill(t.catalog.results, { count: formatPrice(data.count, locale) })}
                </h2>
                <SortLinks locale={locale} t={t} state={state} />
              </div>

              {data.results.length > 0 ? (
                <ul className="mt-6 grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
                  {data.results.map((product, i) => (
                    <ProductCard
                      key={product.id}
                      product={product}
                      locale={locale}
                      t={t}
                      eager={i < 4}
                    />
                  ))}
                </ul>
              ) : (
                <div className="mt-6 rounded-lg border border-border bg-muted p-8 text-center">
                  <p className="font-medium">
                    {narrowing ? t.catalog.noResultsTitle : t.catalog.emptyTitle}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {narrowing ? t.catalog.noResultsText : t.catalog.emptyText}
                  </p>
                  {narrowing && (
                    <Link
                      href={catalogHref(locale, emptyState)}
                      className="mt-4 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground"
                    >
                      {t.catalog.clearAll}
                    </Link>
                  )}
                </div>
              )}

              <Pagination
                locale={locale}
                t={t}
                state={state}
                count={data.count}
                hasNext={data.next !== null}
                hasPrevious={data.previous !== null}
              />
            </>
          ) : (
            <div role="alert" className="rounded-lg border border-border bg-muted p-8 text-center">
              <h2 id="results-heading" className="font-medium">
                {t.catalog.errorTitle}
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">{t.catalog.errorText}</p>
              <Link
                href={catalogHref(locale, state)}
                className="mt-4 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground"
              >
                {t.catalog.retry}
              </Link>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
