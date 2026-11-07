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

  if (slug === "support") {
    return (
      <div className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
        <h1
          dir="ltr"
          className="mb-6 flex items-center justify-center gap-3 text-center text-3xl font-bold tracking-tight sm:mb-8 sm:text-4xl"
        >
          <AboutHeadingDots />
          <span dir="rtl">{t.pages.support}</span>
          <AboutHeadingDots reverse />
        </h1>

        <section
          aria-label="پشتیبانی ودزمانی"
          dir="rtl"
          className="rounded-3xl border border-border bg-muted/70 px-5 py-7 shadow-sm sm:px-8 sm:py-9 md:px-10 md:py-10"
        >
          <div className="mx-auto max-w-2xl space-y-7 text-center text-base leading-8 text-foreground sm:space-y-8 sm:text-lg sm:leading-9">
            <div className="space-y-3">
              <h2 className="text-xl font-bold sm:text-2xl">پشتیبانی ودزمانی</h2>
              <p className="font-semibold">ما در ودزمانی همیشه کنار شما هستیم.</p>
              <p>
                رضایت شما اولویت ماست. اگر درباره محصولات، ثبت سفارش، پرداخت، ارسال یا پیگیری سفارش خود سؤالی دارید،
                تیم پشتیبانی ودزمانی آماده پاسخ‌گویی و راهنمایی شماست.
              </p>
              <p>
                هدف ما این است که تجربه‌ای آسان، مطمئن و لذت‌بخش از خرید آنلاین برای شما فراهم کنیم.
              </p>
            </div>

            <div className="space-y-4">
              <h2 className="text-xl font-bold sm:text-2xl">راه‌های ارتباط با ما</h2>
              <p>
                برای دریافت راهنمایی و ارتباط مستقیم با کارشناسان پشتیبانی، می‌توانید از طریق شماره‌های زیر با ما در تماس باشید:
              </p>
              <div className="mx-auto grid max-w-lg gap-4 sm:grid-cols-2">
                <a
                  href="tel:+989396368307"
                  dir="rtl"
                  className="rounded-2xl border border-border bg-background/70 px-4 py-4 transition-colors hover:bg-background"
                >
                  <span className="mb-1 block text-sm text-muted-foreground">📞 شماره تماس اول</span>
                  <span className="font-semibold tabular-nums">۰۹۳۹۶۳۶۸۳۰۷</span>
                </a>
                <a
                  href="tel:+989016241042"
                  dir="rtl"
                  className="rounded-2xl border border-border bg-background/70 px-4 py-4 transition-colors hover:bg-background"
                >
                  <span className="mb-1 block text-sm text-muted-foreground">📞 شماره تماس دوم</span>
                  <span className="font-semibold tabular-nums">۰۹۰۱۶۲۴۱۰۴۲</span>
                </a>
              </div>
            </div>

            <div className="space-y-3">
              <p className="font-semibold">صفحه اینستاگرام ما:</p>
              <a
                href="https://www.instagram.com/vedzmani/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-background/70 px-5 py-2.5 font-semibold transition-colors hover:bg-background"
              >
                <svg
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                >
                  <rect x="3" y="3" width="18" height="18" rx="5" />
                  <circle cx="12" cy="12" r="4" />
                  <circle cx="18" cy="6" r="1" fill="currentColor" stroke="none" />
                </svg>
                <span>صفحه اینستاگرام</span>
              </a>
            </div>

            <div className="space-y-3 border-t border-border pt-6">
              <h2 className="text-xl font-bold sm:text-2xl">همراه شما هستیم</h2>
              <p>از انتخاب محصول تا دریافت سفارش، در تمام مراحل خرید همراه شما خواهیم بود.</p>
              <p className="font-bold">ودزمانی؛ تجربه‌ای متفاوت از خرید آنلاین.</p>
            </div>
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
