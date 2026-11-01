import Image from "next/image";
import Link from "next/link";
import type { Locale } from "@/i18n/config";
import type { HomepageCategory } from "@/lib/homepage";

export function HomeCategoryGrid({
  locale,
  categories,
}: {
  locale: Locale;
  categories: HomepageCategory[];
}) {
  return (
    <section aria-labelledby="home-categories" className="mx-auto max-w-5xl px-4 py-8">
      <h2
        id="home-categories"
        className="mb-5 text-right text-2xl font-bold tracking-tight sm:text-3xl"
      >
        دسته‌بندی‌ها
      </h2>
      <ul className="grid grid-cols-6 gap-x-3 gap-y-6 sm:gap-x-5 sm:gap-y-8">
        {categories.map((category, index) => {
          const placement =
            index < 3
              ? "col-span-2"
              : index === 3
                ? "col-span-2 col-start-2"
                : "col-span-2 col-start-4";

          return (
            <li key={category.slug} className={placement}>
              <Link
                href={"/" + locale + "/categories/" + encodeURIComponent(category.slug)}
                prefetch={false}
                className="group block text-center focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
              >
                <span className="relative block aspect-square overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition-all duration-200 group-hover:-translate-y-1 group-hover:border-primary/30 group-hover:shadow-lg sm:rounded-3xl">
                  {category.image && (
                    <Image
                      src={category.image.thumbnail_url || category.image.url}
                      alt=""
                      fill
                      unoptimized
                      sizes="(min-width:640px) 16vw, 30vw"
                      className="object-cover transition-transform duration-200 group-hover:scale-[1.04] motion-reduce:transition-none"
                    />
                  )}
                </span>
                <span className="mt-2 block text-sm font-semibold text-foreground sm:mt-3 sm:text-base">
                  {category.name}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
