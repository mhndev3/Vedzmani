import type { Locale } from "@/i18n/config";

/**
 * Sign-in strings. Own module (like checkout.ts) so this flow does not conflict with other
 * storefront work. Both locales must define every key. Wording never claims SMS delivery works:
 * the provider is not configured yet and Django answers 503 in that case (`errors.otp_delivery_unavailable`).
 */
const en = {
  title: "Sign in",
  intro: "Enter your mobile number and we will send you a one-time code.",
  signInLink: "Sign in",
  phone: {
    label: "Mobile number",
    hint: "For example 09123456789",
    submit: "Send code",
    submitting: "Sending code…",
  },
  code: {
    label: "Verification code",
    hint: "6 digits",
    instruction: "Enter the 6-digit code sent to {phone}.",
    submit: "Verify and sign in",
    submitting: "Verifying…",
    change: "Change number",
    resend: "Resend code",
    resendIn: "Resend code in {seconds}",
    resent: "A new code was requested. Use the newest code.",
  },
  done: {
    title: "You are signed in",
    body: "Taking you back…",
    continue: "Continue",
  },
  required: {
    phone: "Enter your mobile number.",
    code: "Enter the verification code.",
  },
  errors: {
    invalid_phone: "Enter a valid Iranian mobile number, for example 09123456789.",
    invalid_code_format: "Enter the 6-digit code.",
    otp_invalid: "That code is not correct. Check it and try again.",
    otp_expired: "This code has expired. Request a new code.",
    otp_consumed: "This code was already used. Request a new code.",
    otp_attempts_exceeded: "Too many incorrect attempts. Request a new code.",
    rate_limited: "Too many requests. Please try again later.",
    rate_limitedWait: "Too many requests. Try again in {time}.",
    otp_delivery_unavailable:
      "We can't send verification codes right now. Please try again later.",
    account_disabled: "This account is disabled. Please contact support.",
    csrf: "Your secure session could not be verified. Reload the page and try again.",
    network: "Could not reach the store. Check your connection and try again.",
    unexpected: "We got an unexpected response. Please try again.",
    generic: "Something went wrong. Please try again.",
    no_session:
      "Your code was accepted but your browser did not keep the sign-in. Make sure cookies are enabled and try again.",
  },
};

type Strings<T> = { [K in keyof T]: T[K] extends string ? string : Strings<T[K]> };
export type AuthDictionary = Strings<typeof en>;

const fa: AuthDictionary = {
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

const dictionaries: Record<Locale, AuthDictionary> = { fa, en };

export function getAuthDictionary(locale: Locale): AuthDictionary {
  return dictionaries[locale];
}
