import Image from "next/image";

export function HomepageHeroSlider() {
  return (
    <section aria-label="بنر ویژه ودزمانی" className="mx-auto w-full max-w-[1440px] px-3 pt-4 sm:px-6 sm:pt-6">
      <div className="relative aspect-[2048/746] overflow-hidden rounded-2xl bg-black">
        <Image
          src="/images/vedzmani-banner.webp"
          alt="نشان ودزمانی"
          fill
          priority
          sizes="(max-width: 768px) 100vw, 1440px"
          className="object-cover"
        />
      </div>
      <h1 className="sr-only">فروشگاه آنلاین ودزمانی</h1>
    </section>
  );
}
