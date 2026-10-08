/** Persian is the default locale and the source of truth for the dictionary shape. */
export const fa = {
  meta: {
    title: "Vedzmani | فروشگاه آنلاین مد",
    description: "Vedzmani، فروشگاه آنلاین مد.",
  },
  a11y: {
    skipToContent: "پرش به محتوای اصلی",
    mainNav: "ناوبری اصلی",
    footerNav: "ناوبری پایین صفحه",
    openMenu: "باز کردن منو",
    closeMenu: "بستن منو",
    menuTitle: "منو",
    switchLanguage: "تغییر زبان به English",
    toggleTheme: "حالت تیره",
  },
  nav: {
    home: "خانه",
    about: "درباره ما",
    contact: "تماس با ما",
    returns: "بازگشت کالا",
    faq: "سوالات متداول",
    support: "پشتیبانی",
    profile: "پروفایل",
  },
  home: {
    heroTitle: "به Vedzmani خوش آمدید",
    heroText:
      "فروشگاه آنلاین مد. محصولات و مجموعه‌ها پس از آماده شدن در همین صفحه نمایش داده می‌شوند.",
    emptySection: "این بخش به‌زودی تکمیل می‌شود.",
    sections: {
      categories: "دسته‌بندی‌ها",
      featuredProducts: "محصولات منتخب",
      collections: "کالکشن‌ها و ست‌ها",
      promotions: "تخفیف‌ها و پیشنهادها",
    },
  },
  footer: {
    categories: "دسته‌بندی‌ها",
    store: "فروشگاه",
    customerService: "خدمات مشتریان",
    shoppingGuide: "راهنمای خرید",
    social: "شبکه‌های اجتماعی",
    trust: "اطمینان و مجوزها",
    comingSoon: "به‌زودی",
    instagram: "اینستاگرام",
    whatsapp: "واتساپ",
    rights: "همه حقوق محفوظ است.",
  },
  pages: {
    placeholder:
      "این صفحه هنوز تکمیل نشده است. محتوای نهایی پس از دریافت اطلاعات رسمی فروشگاه اضافه می‌شود.",
    about: "درباره ما",
    contact: "تماس با ما",
    returns: "بازگشت کالا",
    faq: "سوالات متداول",
    support: "پشتیبانی",
  },
  profile: {
    title: "پروفایل",
    phone: "شماره موبایل",
    signedOut: "شما وارد حساب کاربری نشده‌اید.",
    signedOutHint: "ورود با کد یکبار مصرف به‌زودی در همین بخش در دسترس خواهد بود.",
    unavailable: "اطلاعات حساب در حال حاضر در دسترس نیست. لطفاً بعداً دوباره تلاش کنید.",
  },
};

type Widen<T> = T extends string ? string : { [K in keyof T]: Widen<T[K]> };
export type Dictionary = Widen<typeof fa>;
