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
      <h2 id="home-categories" className="mb-4 text-xl font-semibold tracking-tight">
        دسته‌بندی‌ها
      </h2>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-6 sm:gap-4">
        {categories.map((category, index) => (
          <li key={category.slug} className={index < 3 ? "sm:col-span-2" : "sm:col-span-3"}>
            <Link
              href={"/" + locale + "/categories/" + encodeURIComponent(category.slug)}
              prefetch={false}
              className="group relative block aspect-square overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-primary/30 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
            >
              {category.image && (
                <Image
                  src={category.image.thumbnail_url || category.image.url}
                  alt=""
                  fill
                  unoptimized
                  sizes="(min-width:640px) 16vw, 45vw"
                  className="object-contain p-6 transition-transform duration-200 group-hover:scale-[1.03] motion-reduce:transition-none sm:p-8"
                />
              )}
              <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 via-black/25 to-transparent px-3 pb-3 pt-10 text-center text-sm font-semibold text-white">
                {category.name}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
