import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { ApiError } from "@/lib/api";
import { fill, formatPrice, getProducts, parseCatalogState, type CatalogState, type Paginated, type ProductCardData } from "@/lib/catalog";
import { Pagination, SortLinks } from "@/components/storefront/catalog/CatalogControls";
import { ProductCard } from "@/components/storefront/catalog/ProductCard";

type Props = {
  params: Promise<{ locale: string; slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

const CATEGORIES = [
  { name: "دورس", slug: "sweatshirts" },
  { name: "پیراهن", slug: "shirts" },
  { name: "تی شرت", slug: "t-shirts" },
  { name: "هودی", slug: "hoodies" },
  { name: "کاپشن", slug: "coats" },
  { name: "جکت", slug: "jackets" },
  { name: "شلوار جین", slug: "jeans" },
  { name: "شلوار پارچه ای", slug: "trousers" },
  { name: "جاگر", slug: "joggers" },
  { name: "کتونی", slug: "sneakers" },
  { name: "اکسسوری", slug: "accessories" },
] as const;

function categoryData(slug: string) {
  return CATEGORIES.find((item) => item.slug === slug) ?? null;
}

export async function generateMetadata({ params }: Pick<Props, "params">): Promise<Metadata> {
  const { locale, slug } = await params;
  if (!isLocale(locale)) return {};
  const data = await categoryData(slug);
  return { title: data?.name ?? getDictionary(locale).catalog.title };
}

export default async function CategoryPage({ params, searchParams }: Props) {
  const { locale, slug } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  const data = await categoryData(slug);
  if (!data) notFound();

  const queryState = parseCatalogState(await searchParams);
  const state: CatalogState = { ...queryState, category: [slug], page: queryState.page };
  let products: Paginated<ProductCardData> | null = null;
  let outOfRange = false;
  try {
    products = await getProducts(state);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404 && state.page > 1) outOfRange = true;
  }
  if (outOfRange) redirect("/" + locale + "/categories/" + slug);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{data.name}</h1>
          <Link href={'/' + locale + '/products'} className="mt-2 inline-flex text-sm text-muted-foreground hover:text-foreground">مشاهده همه محصولات</Link>
        </div>
      </div>
      <section aria-labelledby="category-results-heading" className="mt-6 min-w-0">
        {products ? (
          <>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <h2 id="category-results-heading" className="text-sm text-muted-foreground" aria-live="polite">
                {fill(t.catalog.results, { count: formatPrice(products.count, locale) })}
              </h2>
              <SortLinks locale={locale} t={t} state={state} basePath={"/" + locale + "/categories/" + slug} />
            </div>
            {products.results.length ? (
              <ul className="mt-6 grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
                {products.results.map((product, index) => <ProductCard key={product.id} product={product} locale={locale} t={t} eager={index < 4} />)}
              </ul>
            ) : (
              <div className="mt-6 rounded-lg border border-border bg-muted p-8 text-center">
                <p className="font-medium">{t.catalog.noResultsTitle}</p>
                <p className="mt-2 text-sm text-muted-foreground">{t.catalog.emptyText}</p>
              </div>
            )}
            <Pagination locale={locale} t={t} state={state} count={products.count} hasNext={products.next !== null} hasPrevious={products.previous !== null} basePath={"/" + locale + "/categories/" + slug} />
          </>
        ) : (
          <div role="alert" className="rounded-lg border border-border bg-muted p-8 text-center">
            <h2 id="category-results-heading" className="font-medium">{t.catalog.errorTitle}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{t.catalog.errorText}</p>
            <Link href={'/' + locale + '/categories/' + slug} className="mt-4 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground">{t.catalog.retry}</Link>
          </div>
        )}
      </section>
    </div>
  );
}
