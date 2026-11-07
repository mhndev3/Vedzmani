import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { isLocale, locales } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { FAQAccordion } from "@/components/storefront/FAQAccordion";

const slugs = ["about", "contact", "returns", "faq", "support"] as const;
type Slug = (typeof slugs)[number];
const isSlug = (v: string): v is Slug => (slugs as readonly string[]).includes(v);

export const dynamicParams = false;

export function generateStaticParams() {
  return locales.flatMap((locale) => slugs.map((slug) => ({ locale, slug })));
}

type Props = { params: Promise<{ locale: string; slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, slug } = await params;
  if (!isLocale(locale) || !isSlug(slug)) return {};
  return { title: getDictionary(locale).pages[slug] };
}

function AboutHeadingDots({ reverse = false }: { reverse?: boolean }) {
  const sizes = reverse
    ? ["h-2 w-2", "h-1.5 w-1.5", "h-1 w-1"]
    : ["h-1 w-1", "h-1.5 w-1.5", "h-2 w-2"];

  return (
    <span aria-hidden="true" className="flex shrink-0 items-center gap-1">
      {sizes.map((size, index) => (
        <span key={index} className={`rounded-full bg-foreground ${size}`} />
      ))}
    </span>
  );
}

/** The About page has its own provisional brand story; other info pages stay placeholders. */
export default async function InfoPage({ params }: Props) {
  const { locale, slug } = await params;
  if (!isLocale(locale) || !isSlug(slug)) notFound();
  const t = getDictionary(locale);

  if (slug === "faq") {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
        <h1
          dir="ltr"
          className="mb-8 flex items-center justify-center gap-3 text-center text-3xl font-bold tracking-tight sm:mb-10 sm:text-4xl"
        >
          <AboutHeadingDots />
          <span dir="rtl">{t.pages.faq}</span>
          <AboutHeadingDots reverse />
        </h1>
        <FAQAccordion />
      </div>
    );
  }

  if (slug === "about") {
    return (
      <div className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
        <h1
          dir="ltr"
          className="mb-6 flex items-center justify-center gap-3 text-3xl font-bold tracking-tight sm:mb-8 sm:text-4xl"
        >
          <AboutHeadingDots />
          <span dir="rtl">{t.pages.about}</span>
          <AboutHeadingDots reverse />
        </h1>

        <section
          aria-label="داستان ودزمانی"
          className="rounded-3xl border border-border bg-muted/70 px-5 py-7 shadow-sm sm:px-8 sm:py-9 md:px-10 md:py-10"
        >
          <div className="mx-auto max-w-2xl space-y-6 text-center text-lg leading-9 text-foreground sm:space-y-7 sm:text-xl sm:leading-10">
            <p>
              به ودزمانی خوش اومدی!
              <br />
              قبل از هرچیزی لازم دونستم اینو بهت بگم که
              <br />
              انتخاب تو نشون دهنده بخشی از شخصیتته
            </p>

            <p>
              تیم ودزمانی شبانه روز در تلاشه مجموعه ای متنوع از محصولات رو براتون فراهم کنه
              تا بتونید با هر سلیقه و هر موقعیتی استایل های ترند و مورد علاقتون رو پیدا کنید.
            </p>

            <p>
              روزمره و کژوال؟ استریت و اسپرت؟ رسمی و کلاسیک؟ اینجا دقیقا همونجاییه که میتونی همشونو ببینی و تهیه کنی!
            </p>

            <p>
              علاوه بر اینا طراحی جذاب، متریال با کیفیت و جزئیات برای تیم ودزمانی خیلی حائز اهمیته.
            </p>

            <p>
              هدف ما فقط فروش لباس نیست! ما میخوایم یه تجربه ی شیرین و متفاوت از خرید آنلاین رو براتون رقم بزنیم.
              تجربه ای لذت بخش و قابل اعتماد.
            </p>

            <p className="font-semibold">
              بهترین نسخه از استایل خودتو اینجا تجربه کن.
            </p>
          </div>
        </section>

      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">{t.pages[slug]}</h1>
      <p className="mt-4 text-muted-foreground">{t.pages.placeholder}</p>
    </div>
  );
}
