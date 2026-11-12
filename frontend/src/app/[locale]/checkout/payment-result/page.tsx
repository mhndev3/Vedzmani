import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ status?: string | string[] }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  return { title: "نتیجه پرداخت", robots: { index: false, follow: false } };
}

export default async function PaymentResultPage({ params, searchParams }: Props) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();

  const query = await searchParams;
  const rawStatus = Array.isArray(query.status) ? query.status[0] : query.status;
  const status = rawStatus === "success" || rawStatus === "pending" ? rawStatus : "failed";

  const content = status === "success"
    ? {
        title: "پرداخت با موفقیت تأیید شد",
        body: "پرداخت توسط درگاه تأیید شده است. سفارش شما پس از ثبت تأیید نهایی نمایش داده می‌شود.",
      }
    : status === "pending"
      ? {
          title: "نتیجه پرداخت در حال بررسی است",
          body: "پاسخ نهایی درگاه هنوز دریافت نشده است. از پرداخت دوباره خودداری کنید و وضعیت را بعداً بررسی کنید.",
        }
      : {
          title: "پرداخت تأیید نشد",
          body: "پرداخت تکمیل یا تأیید نشد. اگر مبلغی از حساب شما کسر شده، تا مشخص شدن وضعیت تراکنش دوباره پرداخت نکنید.",
        };

  return (
    <main className="mx-auto max-w-xl px-4 py-16 text-center">
      <section className="rounded-xl border border-border p-6 sm:p-8">
        <h1 className="text-2xl font-semibold">{content.title}</h1>
        <p className="mt-4 leading-8 text-muted-foreground">{content.body}</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href={`/${locale}/orders`} className="inline-flex items-center justify-center rounded-lg bg-primary px-5 py-3 text-sm font-medium text-primary-foreground">
            مشاهده سفارش‌ها
          </Link>
          <Link href={`/${locale}/products`} className="inline-flex items-center justify-center rounded-lg border border-border px-5 py-3 text-sm">
            بازگشت به فروشگاه
          </Link>
        </div>
      </section>
    </main>
  );
}
