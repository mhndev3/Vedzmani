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
    <section aria-labelledby="home-categories" className="mx-auto max-w-6xl px-4 py-8">
      <h2 id="home-categories" className="mb-4 text-xl font-semibold tracking-tight">
        دسته‌بندی‌ها
      </h2>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {categories.map((category) => (
          <li key={category.slug}>
            <Link
              href={"/" + locale + "/categories/" + encodeURIComponent(category.slug)}
              className="group relative block aspect-square overflow-hidden rounded-2xl bg-muted focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
            >
              {category.image && (
                <Image
                  src={category.image.thumbnail_url || category.image.url}
                  alt=""
                  fill
                  sizes="(min-width:1024px) 18vw, (min-width:640px) 30vw, 45vw"
                  className="object-cover transition-transform duration-200 group-hover:scale-[1.03] motion-reduce:transition-none"
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
