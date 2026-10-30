import type { Locale } from "@/i18n/config";

type Strings<T> = { [K in keyof T]: T[K] extends string ? string : Strings<T[K]> };

const fa = {
  title: "ورود",
  intro: "شماره موبایل خود را وارد کنید تا یک کد یک‌بارمصرف برایتان ارسال شود.",
  signInLink: "ورود",
  phone: {
    label: "شماره موبایل",
    hint: "مثلاً 09123456789",
    submit: "ارسال کد",
    submitting: "در حال ارسال کد…",
  },
  code: {
    label: "کد تأیید",
    hint: "۶ رقم",
    instruction: "کد ۶ رقمی ارسال‌شده به {phone} را وارد کنید.",
    submit: "تأیید و ورود",
    submitting: "در حال بررسی…",
    change: "تغییر شماره",
    resend: "ارسال دوباره کد",
    resendIn: "ارسال دوباره کد تا {seconds} دیگر",
    resent: "کد جدید درخواست شد. از آخرین کد استفاده کنید.",
  },
  done: {
    title: "وارد شدید",
    body: "در حال بازگشت به صفحه قبل…",
    continue: "ادامه",
  },
  required: {
    phone: "شماره موبایل را وارد کنید.",
    code: "کد تأیید را وارد کنید.",
  },
  errors: {
    invalid_phone: "یک شماره موبایل معتبر ایران وارد کنید، مثلاً 09123456789.",
    invalid_code_format: "کد ۶ رقمی را وارد کنید.",
    otp_invalid: "کد وارد‌شده درست نیست. آن را بررسی و دوباره تلاش کنید.",
    otp_expired: "این کد منقضی شده است. کد جدید درخواست کنید.",
    otp_consumed: "این کد قبلاً استفاده شده است. کد جدید درخواست کنید.",
    otp_attempts_exceeded: "تعداد تلاش‌های نادرست زیاد بود. کد جدید درخواست کنید.",
    rate_limited: "تعداد درخواست‌ها زیاد است. لطفاً بعداً دوباره تلاش کنید.",
    rate_limitedWait: "تعداد درخواست‌ها زیاد است. {time} دیگر دوباره تلاش کنید.",
    otp_delivery_unavailable: "در حال حاضر ارسال کد تأیید ممکن نیست. لطفاً بعداً دوباره تلاش کنید.",
    account_disabled: "این حساب غیرفعال است. لطفاً با پشتیبانی تماس بگیرید.",
    csrf: "نشست امن شما تأیید نشد. صفحه را دوباره بارگذاری کنید و دوباره تلاش کنید.",
    network: "ارتباط با فروشگاه برقرار نشد. اتصال خود را بررسی و دوباره تلاش کنید.",
    unexpected: "پاسخ غیرمنتظره‌ای دریافت شد. لطفاً دوباره تلاش کنید.",
    generic: "مشکلی پیش آمد. لطفاً دوباره تلاش کنید.",
    no_session:
      "کد شما پذیرفته شد اما مرورگر ورود را نگه نداشت. مطمئن شوید کوکی‌ها فعال است و دوباره تلاش کنید.",
  },
};

export type AuthDictionary = Strings<typeof fa>;

export function getAuthDictionary(_locale: Locale): AuthDictionary {
  return fa;
}
