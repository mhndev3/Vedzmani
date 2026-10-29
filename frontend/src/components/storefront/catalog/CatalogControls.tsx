import Form from "next/form";
import Link from "next/link";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import {
  SORTS,
  catalogHref,
  fill,
  formatPrice,
  stateToParams,
  totalPages,
  type CatalogState,
  type FilterOptions,
} from "@/lib/catalog";

const inputClass =
  "h-10 w-full rounded-lg border border-border bg-background px-3 text-sm placeholder:text-muted-foreground";
const buttonClass =
  "inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90";

/** Hidden inputs that carry the rest of the URL state through a GET form (page is always reset). */
function carry(state: CatalogState, omit: "search" | "filters") {
  const p = stateToParams({ ...state, page: 1 });
  if (omit === "search") p.delete("search");
  else for (const k of ["category", "collection", "color", "size", "min_price", "max_price", "in_stock"]) p.delete(k);
  return [...p.entries()].map(([k, v]) => <input key={k} type="hidden" name={k} value={v} />);
}

export function SearchForm({
  locale,
  t,
  state,
}: {
  locale: Locale;
  t: Dictionary;
  state: CatalogState;
}) {
  return (
    <Form
      key={JSON.stringify(state)}
      action={`/${locale}/products`}
      role="search"
      className="flex w-full max-w-xl gap-2"
    >
      {carry(state, "search")}
      <label htmlFor="catalog-search" className="sr-only">
        {t.catalog.searchLabel}
      </label>
      <input
        id="catalog-search"
        type="search"
        name="search"
        defaultValue={state.search}
        maxLength={100}
        placeholder={t.catalog.searchPlaceholder}
        className={inputClass}
      />
      <button type="submit" className={buttonClass}>
        {t.catalog.searchButton}
      </button>
    </Form>
  );
}

function CheckGroup({
  legend,
  name,
  items,
  selected,
  swatch,
}: {
  legend: string;
  name: string;
  items: { value: string; label: string; hex?: string }[];
  selected: string[];
  swatch?: boolean;
}) {
  if (items.length === 0) return null;
  return (
    <fieldset className="min-w-0 border-t border-border pt-4">
      <legend className="mb-2 text-sm font-semibold">{legend}</legend>
      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item.value}>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                name={name}
                value={item.value}
                defaultChecked={selected.includes(item.value)}
                className="size-4 accent-[var(--primary)]"
              />
              {swatch && (
                <span
                  aria-hidden="true"
                  className="size-3.5 shrink-0 rounded-full border border-border"
                  style={item.hex ? { backgroundColor: item.hex } : undefined}
                />
              )}
              <span className="min-w-0 break-words">{item.label}</span>
            </label>
          </li>
        ))}
      </ul>
    </fieldset>
  );
}

/** Only values that exist on published products are offered (from /api/catalog/filters/). */
export function FilterForm({
  locale,
  t,
  state,
  options,
}: {
  locale: Locale;
  t: Dictionary;
  state: CatalogState;
  options: FilterOptions;
}) {
  return (
    <Form
      key={JSON.stringify(state)}
      action={`/${locale}/products`}
      className="flex flex-col gap-4"
    >
      {carry(state, "filters")}
      <CheckGroup
        legend={t.catalog.category}
        name="category"
        selected={state.category}
        items={options.categories.map((c) => ({ value: c.slug, label: c.name }))}
      />
      <CheckGroup
        legend={t.catalog.collection}
        name="collection"
        selected={state.collection}
        items={options.collections.map((c) => ({ value: c.slug, label: c.name }))}
      />
      <CheckGroup
        legend={t.catalog.color}
        name="color"
        selected={state.color}
        swatch
        items={options.colors.map((c) => ({ value: c.slug, label: c.name, hex: c.hex_color }))}
      />
      <CheckGroup
        legend={t.catalog.size}
        name="size"
        selected={state.size}
        items={options.sizes.map((s) => ({ value: s.code, label: s.label }))}
      />
      <fieldset className="min-w-0 border-t border-border pt-4">
        <legend className="mb-2 text-sm font-semibold">{t.catalog.price}</legend>
        <div className="flex gap-2">
          <div className="min-w-0 flex-1">
            <label htmlFor="min_price" className="mb-1 block text-xs text-muted-foreground">
              {t.catalog.minPrice}
            </label>
            <input
              id="min_price"
              name="min_price"
              type="number"
              inputMode="numeric"
              min={0}
              defaultValue={state.minPrice}
              className={inputClass}
            />
          </div>
          <div className="min-w-0 flex-1">
            <label htmlFor="max_price" className="mb-1 block text-xs text-muted-foreground">
              {t.catalog.maxPrice}
            </label>
            <input
              id="max_price"
              name="max_price"
              type="number"
              inputMode="numeric"
              min={0}
              defaultValue={state.maxPrice}
              className={inputClass}
            />
          </div>
        </div>
      </fieldset>
      <label className="flex cursor-pointer items-center gap-2 border-t border-border pt-4 text-sm">
        <input
          type="checkbox"
          name="in_stock"
          value="true"
          defaultChecked={state.inStock}
          className="size-4 accent-[var(--primary)]"
        />
        {t.catalog.inStockOnly}
      </label>
      <button type="submit" className={buttonClass}>
        {t.catalog.applyFilters}
      </button>
    </Form>
  );
}

export function SortLinks({
  locale,
  t,
  state,
}: {
  locale: Locale;
  t: Dictionary;
  state: CatalogState;
}) {
  return (
    <nav aria-label={t.catalog.sortLabel}>
      <p className="mb-1 text-xs text-muted-foreground" aria-hidden="true">
        {t.catalog.sortLabel}
      </p>
      <ul className="flex flex-wrap gap-1.5">
        {SORTS.map((s) => {
          const current = state.sort === s;
          return (
            <li key={s}>
              <Link
                href={catalogHref(locale, { ...state, sort: s, page: 1 })}
                prefetch={false}
                aria-current={current ? "true" : undefined}
                className={`inline-flex h-9 items-center rounded-full border px-3 text-sm ${
                  current
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border hover:bg-muted"
                }`}
              >
                {t.catalog.sort[s]}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function Pagination({
  locale,
  t,
  state,
  count,
  hasNext,
  hasPrevious,
}: {
  locale: Locale;
  t: Dictionary;
  state: CatalogState;
  count: number;
  hasNext: boolean;
  hasPrevious: boolean;
}) {
  const total = totalPages(count);
  if (total <= 1) return null;
  const linkClass =
    "inline-flex h-10 min-w-24 items-center justify-center rounded-lg border border-border px-4 text-sm hover:bg-muted";
  const disabledClass =
    "inline-flex h-10 min-w-24 items-center justify-center rounded-lg border border-border px-4 text-sm text-muted-foreground opacity-50";
  return (
    <nav aria-label={t.catalog.pagination} className="mt-10 flex items-center justify-between gap-3">
      {hasPrevious ? (
        <Link
          rel="prev"
          prefetch={false}
          href={catalogHref(locale, { ...state, page: state.page - 1 })}
          className={linkClass}
        >
          {t.catalog.previous}
        </Link>
      ) : (
        <span aria-disabled="true" className={disabledClass}>
          {t.catalog.previous}
        </span>
      )}
      <p className="text-sm text-muted-foreground" aria-current="page">
        {fill(t.catalog.pageOf, {
          page: formatPrice(state.page, locale),
          total: formatPrice(total, locale),
        })}
      </p>
      {hasNext ? (
        <Link
          rel="next"
          prefetch={false}
          href={catalogHref(locale, { ...state, page: state.page + 1 })}
          className={linkClass}
        >
          {t.catalog.next}
        </Link>
      ) : (
        <span aria-disabled="true" className={disabledClass}>
          {t.catalog.next}
        </span>
      )}
    </nav>
  );
}
