import type { Locale } from "@/i18n/config";

type Strings<T> = { [K in keyof T]: T[K] extends string ? string : Strings<T[K]> };

const fa = {
  title: "تکمیل خرید",
  intro: "برای مشاهده و تکمیل اطلاعات خرید، وارد حساب کاربری شوید یا حساب بسازید. ثبت نهایی سفارش در حال حاضر غیرفعال است.",
  loading: "در حال بارگذاری صفحه تکمیل خرید…",
  unavailable: {
    title: "سبد خرید در حال حاضر قابل انتقال نیست",
    body: "ممکن است یک کالا ناموجود شده یا موجودی آن تغییر کرده باشد. سبد خرید را بررسی کنید و دوباره تلاش کنید.",
    retry: "بررسی دوباره",
    backToCart: "بازگشت به سبد خرید",
  },
  signIn: {
    title: "برای ادامه وارد شوید یا حساب بسازید",
    body: "با شماره موبایل خود ادامه دهید. اگر حسابی نداشته باشید، پس از تأیید شماره برایتان ایجاد می‌شود.",
  },
  empty: {
    title: "سبد خرید شما خالی است",
    body: "پیش از تکمیل خرید، محصولاتی به سبد خرید اضافه کنید.",
    browse: "مشاهده محصولات",
  },
  summary: {
    title: "خلاصه خرید",
    quantity: "تعداد: {quantity}",
    itemsTotal: "جمع کالاها",
    shippingNote: "هزینه ارسال شامل نمی‌شود و پس از تعیین روش ارسال مشخص خواهد شد.",
    unavailableLine: "این کالا دیگر موجود نیست",
    insufficientLine: "موجودی این کالا کافی نیست",
    issues: "برخی اقلام نیاز به بررسی دارند. امکان ادامه ثبت سفارش تا رفع مشکل وجود ندارد.",
  },
  form: {
    title: "اطلاعات تحویل",
    recipient_name: "نام گیرنده",
    province: "استان",
    city: "شهر",
    address: "نشانی کامل",
    postal_code: "کد پستی",
    postalHint: "۱۰ رقم",
    phoneNote: "شماره تماس ثبت‌شده در حساب شما: {phone}",
  },
  disabledNote: "اطلاعات این بخش برای آماده‌سازی خرید نمایش داده می‌شود. ثبت سفارش و پرداخت هنوز فعال نشده‌اند؛ هیچ سفارشی ساخته نمی‌شود و مبلغی دریافت نخواهد شد.",
};

export type CheckoutDictionary = Strings<typeof fa>;
export function getCheckoutDictionary(_locale: Locale): CheckoutDictionary { return fa; }
export function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(vars[key] ?? ""));
}
