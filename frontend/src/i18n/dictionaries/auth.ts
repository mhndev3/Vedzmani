import type { Locale } from "@/i18n/config";
type Strings<T> = { [K in keyof T]: T[K] extends string ? string : Strings<T[K]> };
const fa = {
 title: "حساب کاربری ودزمانی",
 intro: "برای ادامه خرید، وارد حساب خود شوید یا یک حساب تازه بسازید.",
 signInLink: "ورود / ساخت حساب",
 phone: { label: "شماره موبایل", hint: "مثلاً 09123456789", submit: "دریافت کد تأیید", submitting: "در حال ارسال..." },
 code: { label: "کد تأیید پیامکی", hint: "کد ۶ رقمی ارسال‌شده را وارد کنید.", instruction: "کد ارسال‌شده به {phone} را وارد کنید.", submit: "تأیید شماره و ادامه", submitting: "در حال بررسی…", change: "ویرایش شماره", resend: "ارسال دوباره کد", resendIn: "ارسال دوباره کد تا {seconds} دیگر", resent: "درخواست ارسال کد جدید ثبت شد." },
 password: { label: "رمز عبور", confirm: "تکرار رمز عبور", submit: "ورود به حساب کاربری", create: "ثبت رمز عبور", creating: "در حال ثبت رمز…", forgot: "رمز عبور را فراموش کرده‌اید؟", newTitle: "برای حساب خود رمز بسازید", newHint: "حداقل ۱۰ کاراکتر؛ بهتر است ترکیبی از حروف و عدد باشد.", mismatch: "رمزهای عبور یکسان نیستند.", show: "نمایش رمز", hide: "مخفی کردن رمز" },
 modes: { signup: "ثبت‌نام", login: "ورود", signupHint: "حسابی ندارید؟", loginHint: "قبلاً حساب ساخته‌اید؟", switchLogin: "ورود به حساب", switchSignup: "ساخت حساب جدید" },
 done: { title: "ورود موفق", body: "در حال انتقال به فروشگاه…", continue: "ادامه" },
 required: { phone: "شماره موبایل را وارد کنید.", code: "کد تأیید را وارد کنید.", password: "رمز عبور را وارد کنید." },
 errors: {
 invalid_phone: "یک شماره موبایل معتبر ایران وارد کنید، مثلاً 09123456789.", invalid_code_format: "کد تأیید باید ۶ رقم باشد.", otp_invalid: "کد واردشده درست نیست.", otp_expired: "کد منقضی شده است. کد جدید درخواست کنید.", otp_consumed: "این کد قبلاً استفاده شده است.", otp_attempts_exceeded: "تعداد تلاش‌های نادرست زیاد بود. کد جدید درخواست کنید.", rate_limited: "تعداد درخواست‌ها زیاد است. کمی بعد دوباره تلاش کنید.", rate_limitedWait: "تعداد درخواست‌ها زیاد است. {time} دیگر دوباره تلاش کنید.", otp_delivery_unavailable: "ارسال پیامک فعلاً فعال نیست. سرویس پیامک هنوز به فروشگاه متصل نشده است.", account_disabled: "این حساب امکان ورود ندارد. با پشتیبانی تماس بگیرید.", invalid_credentials: "شماره موبایل یا رمز عبور اشتباه است.", weak_password: "رمز عبور با شرایط امنیتی مطابقت ندارد.", csrf: "نشست امن تأیید نشد. صفحه را دوباره بارگذاری کنید.", network: "ارتباط با فروشگاه برقرار نشد. اتصال را بررسی کنید.", unexpected: "پاسخ غیرمنتظره‌ای دریافت شد. دوباره تلاش کنید.", generic: "مشکلی پیش آمد. دوباره تلاش کنید.", no_session: "ورود تأیید شد اما نشست مرورگر برقرار نشد. کوکی‌ها را فعال کنید."
 }
};
export type AuthDictionary = Strings<typeof fa>;
export function getAuthDictionary(_locale: Locale): AuthDictionary { return fa; }
