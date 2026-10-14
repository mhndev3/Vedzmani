import type { Locale } from "@/i18n/config";

/**
 * Checkout strings. Kept in their own module (not in fa.ts/en.ts) so this flow
 * never conflicts with other storefront work. Both locales must define every key.
 * Wording follows backend/ORDERS.md: totals exclude shipping, payment is "unpaid".
 */
const en = {
  title: "Checkout",
  intro: "Enter your delivery details to place your order. No payment is taken at this step.",
  loading: "Loading your checkout…",
  unavailable: {
    title: "Checkout is temporarily unavailable",
    body: "We couldn't load your checkout. Please try again.",
    retry: "Try again",
  },
  signIn: {
    title: "Sign in to continue",
    body: "You need to be signed in to place an order.",
    recheck: "I've signed in, check again",
  },
  empty: {
    title: "Your cart is empty",
    body: "Add items to your cart before checking out.",
    browse: "Browse products",
  },
  maybePlaced: {
    title: "Please check before ordering again",
    body: "Your cart is now empty. If you just submitted an order it may already have been placed, so do not order again. Contact support to confirm.",
    browse: "Browse products",
  },
  summary: {
    title: "Order summary",
    quantity: "Qty {quantity}",
    itemsTotal: "Items total",
    shippingNote:
      "Shipping is not included. A delivery fee has not been decided yet, so this is not the final delivered price.",
    paymentNote: "No payment is taken here. Your order will be created as unpaid.",
    unavailableLine: "No longer available",
    insufficientLine: "Not enough stock",
    issues:
      "Some items in your cart are unavailable or exceed current stock. Update your cart before ordering.",
  },
  form: {
    title: "Delivery details",
    recipient_name: "Recipient name",
    province: "Province",
    city: "City",
    address: "Address",
    postal_code: "Postal code",
    postalHint: "10 digits",
    phoneNote: "We use the phone number on your account for delivery contact: {phone}",
    submit: "Place order",
    submitting: "Placing your order…",
  },
  fieldErrors: {
    required: "This field is required.",
    too_long: "Must be at most {max} characters.",
    invalid_postal_code: "Enter a 10-digit postal code.",
    invalid_characters: "Remove line breaks or control characters.",
    invalid: "Please check this value.",
  },
  errorsTitle: "Please fix the highlighted fields.",
  banners: {
    csrf: "Your session expired. Please submit again.",
    csrfUnavailable: "We couldn't prepare a secure request. Check your connection and try again.",
    item_unavailable:
      "One or more items in your cart are no longer available. Your order was not placed. Please update your cart.",
    insufficient_stock:
      "There isn't enough stock for one or more items. Your order was not placed. Please update your cart.",
    ambiguous:
      "We couldn't confirm whether your order was placed. Please check before submitting again.",
    server: "Something went wrong and your order was not placed. Please try again.",
  },
  confirmation: {
    title: "Order placed",
    thanks: "Thank you. Your order has been created.",
    number: "Order number",
    status: "Status",
    payment: "Payment",
    delivery: "Delivery details",
    phone: "Contact phone",
    items: "Items",
    total: "Items total (excludes shipping)",
    paymentLabels: { unpaid: "Not paid. No payment has been taken." },
    statusLabels: { pending: "Pending" },
    continue: "Continue shopping",
  },
};

type Strings<T> = { [K in keyof T]: T[K] extends string ? string : Strings<T[K]> };
export type CheckoutDictionary = Strings<typeof en>;

const fa: CheckoutDictionary = {
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

const dictionaries: Record<Locale, CheckoutDictionary> = { fa, en };

export function getCheckoutDictionary(locale: Locale): CheckoutDictionary {
  return dictionaries[locale];
}

export function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(vars[key] ?? ""));
}
