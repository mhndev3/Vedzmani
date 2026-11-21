import Image from "next/image";
import Link from "next/link";

export type HomepageBanner = {
  id: number;
  title: string;
  subtitle: string;
  alt_text: string;
  desktop_image: string;
  mobile_image: string | null;
  cta_label: string;
  cta_url: string;
};

export function HomepageHeroSlider({ banners = [] }: { banners?: HomepageBanner[] }) {
  if (banners.length === 0) {
    return (
      <section aria-label="بنر ویژه ودزمانی" className="mx-auto w-full max-w-[1440px] px-3 pt-4 sm:px-6 sm:pt-6">
        <div className="relative block aspect-[2048/746] overflow-hidden rounded-2xl bg-black">
          <Image src="/images/vedzmani-banner-vz.svg" alt="نشان ودزمانی" fill priority sizes="(max-width: 768px) 100vw, 1440px" className="object-cover" />
        </div>
        <h1 className="sr-only">فروشگاه آنلاین ودزمانی</h1>
      </section>
    );
  }

  return (
    <section aria-label="بنرهای ویژه ودزمانی" className="mx-auto w-full max-w-[1440px] px-3 pt-4 sm:px-6 sm:pt-6">
      <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-smooth rounded-2xl" dir="rtl">
        {banners.map((banner, index) => (
          <article key={banner.id} className="relative min-w-full snap-center overflow-hidden rounded-2xl bg-muted">
            <div className="relative aspect-[2048/746]">
              {banner.mobile_image && <picture>
                <source media="(max-width: 639px)" srcSet={banner.mobile_image} />
                <Image src={banner.desktop_image} alt={banner.alt_text} fill priority={index === 0} sizes="(max-width: 768px) 100vw, 1440px" className="object-cover" unoptimized />
              </picture>}
              {!banner.mobile_image && <Image src={banner.desktop_image} alt={banner.alt_text} fill priority={index === 0} sizes="(max-width: 768px) 100vw, 1440px" className="object-cover" unoptimized />}
            </div>
            {(banner.title || banner.subtitle || (banner.cta_label && banner.cta_url)) && (
              <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-end justify-between gap-3 bg-gradient-to-t from-black/75 via-black/25 to-transparent p-4 pt-16 text-white sm:p-7 sm:pt-24">
                <div>{banner.title && <h2 className="text-lg font-bold sm:text-2xl">{banner.title}</h2>}{banner.subtitle && <p className="mt-1 max-w-2xl text-sm leading-6">{banner.subtitle}</p>}</div>
                {banner.cta_label && banner.cta_url && <Link href={banner.cta_url} className="rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-black">{banner.cta_label}</Link>}
              </div>
            )}
          </article>
        ))}
      </div>
      <h1 className="sr-only">فروشگاه آنلاین ودزمانی</h1>
    </section>
  );
}
