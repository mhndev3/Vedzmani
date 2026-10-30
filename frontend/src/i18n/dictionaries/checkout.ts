import type { Locale } from "@/i18n/config";

type Strings<T> = { [K in keyof T]: T[K] extends string ? string : Strings<T[K]> };

const fa = {
  title: "تسویه حساب",
  intro: "برای ثبت سفارش، اطلاعات تحویل را وارد کنید. در این مرحله هیچ پرداختی انجام نمی‌شود.",
  loading: "در حال بارگذاری صفحه تسویه حساب…",
  unavailable: {
    title: "تسویه حساب موقتاً در دسترس نیست",
    body: "بارگذاری تسویه حساب انجام نشد. لطفاً دوباره تلاش کنید.",
    retry: "تلاش دوباره",
  },
  signIn: {
    title: "برای ادامه وارد شوید",
    body: "برای ثبت سفارش باید وارد حساب کاربری خود شده باشید.",
    recheck: "وارد شده‌ام، دوباره بررسی کن",
  },
  empty: {
    title: "سبد خرید شما خالی است",
    body: "پیش از تسویه حساب، محصولاتی به سبد خرید اضافه کنید.",
    browse: "مشاهده محصولات",
  },
  maybePlaced: {
    title: "پیش از سفارش مجدد بررسی کنید",
    body: "سبد خرید شما اکنون خالی است. اگر همین الان سفارشی ثبت کرده‌اید، ممکن است ثبت شده باشد؛ پس دوباره سفارش ندهید و برای اطمینان با پشتیبانی تماس بگیرید.",
    browse: "مشاهده محصولات",
  },
  summary: {
    title: "خلاصه سفارش",
    quantity: "تعداد: {quantity}",
    itemsTotal: "جمع کالاها",
    shippingNote:
      "هزینه ارسال شامل نمی‌شود. هزینه ارسال هنوز تعیین نشده است؛ بنابراین این مبلغ قیمت نهایی تحویل نیست.",
    paymentNote: "در این مرحله پرداختی انجام نمی‌شود. سفارش شما به‌صورت پرداخت‌نشده ثبت می‌شود.",
    unavailableLine: "دیگر موجود نیست",
    insufficientLine: "موجودی کافی نیست",
    issues:
      "برخی کالاهای سبد خرید شما ناموجود است یا از موجودی فعلی بیشتر است. پیش از ثبت سفارش سبد خرید را اصلاح کنید.",
  },
  form: {
    title: "اطلاعات تحویل",
    recipient_name: "نام گیرنده",
    province: "استان",
    city: "شهر",
    address: "نشانی",
    postal_code: "کد پستی",
    postalHint: "۱۰ رقم",
    phoneNote: "برای تماس هنگام تحویل از شماره تلفن حساب شما استفاده می‌شود: {phone}",
    submit: "ثبت سفارش",
    submitting: "در حال ثبت سفارش…",
  },
  fieldErrors: {
    required: "این فیلد الزامی است.",
    too_long: "حداکثر {max} نویسه مجاز است.",
    invalid_postal_code: "کد پستی ۱۰ رقمی وارد کنید.",
    invalid_characters: "خط جدید یا نویسه‌های کنترلی را حذف کنید.",
    invalid: "لطفاً این مقدار را بررسی کنید.",
  },
  errorsTitle: "لطفاً فیلدهای مشخص‌شده را اصلاح کنید.",
  banners: {
    csrf: "نشست شما منقضی شده است. لطفاً دوباره ثبت کنید.",
    csrfUnavailable: "ایجاد درخواست امن ممکن نشد. اتصال خود را بررسی و دوباره تلاش کنید.",
    item_unavailable:
      "یک یا چند کالای سبد خرید شما دیگر موجود نیست. سفارش ثبت نشد. لطفاً سبد خرید را اصلاح کنید.",
    insufficient_stock:
      "موجودی یک یا چند کالا کافی نیست. سفارش ثبت نشد. لطفاً سبد خرید را اصلاح کنید.",
    ambiguous: "نتوانستیم تأیید کنیم که سفارش ثبت شده است یا نه. پیش از ثبت مجدد، لطفاً بررسی کنید.",
    server: "مشکلی پیش آمد و سفارش ثبت نشد. لطفاً دوباره تلاش کنید.",
  },
  confirmation: {
    title: "سفارش ثبت شد",
    thanks: "سپاس از شما. سفارش شما ایجاد شد.",
    number: "شماره سفارش",
    status: "وضعیت",
    payment: "پرداخت",
    delivery: "اطلاعات تحویل",
    phone: "تلفن تماس",
    items: "کالاها",
    total: "جمع کالاها (بدون هزینه ارسال)",
    paymentLabels: { unpaid: "پرداخت نشده. هیچ مبلغی دریافت نشده است." },
    statusLabels: { pending: "در انتظار" },
    continue: "ادامه خرید",
  },
};

export type CheckoutDictionary = Strings<typeof fa>;

export function getCheckoutDictionary(_locale: Locale): CheckoutDictionary {
  return fa;
}

export function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(vars[key] ?? ""));
}
