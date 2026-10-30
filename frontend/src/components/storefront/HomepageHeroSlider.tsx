import Image from "next/image";
import Link from "next/link";
import type { Locale } from "@/i18n/config";

export function HomepageHeroSlider({ locale }: { locale: Locale }) {
  return (
    <section aria-label="بنر ویژه ودزمانی" className="mx-auto w-full max-w-[1440px] px-3 pt-4 sm:px-6 sm:pt-6">
      <Link
        href={`/${locale}/products`}
        aria-label="مشاهده همه محصولات"
        className="relative block aspect-[2048/746] overflow-hidden rounded-2xl bg-black focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
      >
        <Image
          src="/images/vedzmani-banner.webp"
          alt="نشان ودزمانی"
          fill
          priority
          sizes="(max-width: 768px) 100vw, 1440px"
          className="object-cover"
        />
      </Link>
      <h1 className="sr-only">فروشگاه آنلاین ودزمانی</h1>
    </section>
  );
}
