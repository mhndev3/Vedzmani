"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { authApi } from "@/lib/auth/api";
import type { AuthUser } from "@/lib/auth/api";
import ProductRemovalManager from "./ProductRemovalManager";

export default function AdminWorkspacePage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let active = true;
    authApi.me().then((current) => {
      if (!active) return;
      if (!current?.is_staff) {
        setUser(null);
        setChecking(false);
        return;
      }
      setUser(current);
      setChecking(false);
    }).catch(() => {
      if (active) {
        setUser(null);
        setChecking(false);
      }
    });
    return () => { active = false; };
  }, []);

  if (checking) {
    return <main dir="rtl" className="mx-auto w-full max-w-6xl px-4 py-16 text-center text-muted-foreground">در حال بررسی دسترسی مدیریت…</main>;
  }

  if (!user) {
    return (
      <main dir="rtl" className="mx-auto flex w-full max-w-xl flex-col items-center px-4 py-20 text-center">
        <div className="mb-4 flex size-14 items-center justify-center rounded-2xl bg-muted text-2xl" aria-hidden="true">🔒</div>
        <h1 className="text-2xl font-bold">دسترسی مدیریت</h1>
        <p className="mt-3 text-sm leading-7 text-muted-foreground">برای ورود به پنل مدیریت باید با حساب دارای دسترسی مدیریتی وارد شوید.</p>
        <Link href={"/" + locale + "/sign-in?next=/" + locale + "/admin-panel"} className="mt-6 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground">ورود مدیر</Link>
        <button type="button" onClick={() => router.push("/" + locale)} className="mt-3 rounded-xl px-5 py-2 text-sm text-muted-foreground hover:bg-muted">بازگشت به فروشگاه</button>
      </main>
    );
  }

  return (
    <main dir="rtl" className="mx-auto w-full max-w-6xl px-4 py-8 sm:py-12">
      <div className="flex flex-col gap-4 border-b border-border pb-7 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">فضای مدیریت ودزمانی</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">پنل مدیریت</h1>
          <p className="mt-2 text-sm text-muted-foreground">مدیریت فروشگاه از یک فضای یکپارچه</p>
        </div>
        <Link href={"/" + locale + "?admin=1"} className="inline-flex w-fit items-center rounded-xl border border-border px-4 py-2.5 text-sm font-medium hover:bg-muted">مشاهده فروشگاه در حالت مدیریت</Link>
      </div>

      <section className="mt-7 rounded-2xl border border-border bg-card p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">حساب مدیر</h2>
            <p className="mt-1 text-sm text-muted-foreground" dir="ltr">{user.phone}</p>
          </div>
          <span className="rounded-full bg-muted px-3 py-1.5 text-xs font-semibold">دسترسی مدیریتی تأیید شد</span>
        </div>
      </section>

      <Link href={"/" + locale + "/admin-panel/catalog"} className="mt-7 flex items-center justify-between gap-4 rounded-2xl border border-primary/30 bg-primary/5 p-5 transition hover:bg-primary/10">
        <div><h2 className="font-bold">مدیریت اختصاصی محصولات</h2><p className="mt-1 text-sm text-muted-foreground">ساخت و ویرایش محصول، رنگ‌بندی، سایزبندی و کنترل موجودی</p></div>
        <span className="shrink-0 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground">ورود به کاتالوگ ←</span>
      </Link>

      <Link href={"/" + locale + "/admin-panel/catalog/taxonomy"} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 transition hover:bg-muted">
        <div><h2 className="font-bold">مدیریت دسته‌بندی‌ها و مجموعه‌ها</h2><p className="mt-1 text-sm text-muted-foreground">ساخت، ویرایش، مرتب‌سازی و فعال‌سازی ساختار کاتالوگ</p></div>
        <span className="shrink-0 rounded-xl border border-border px-4 py-2.5 text-sm font-semibold">مدیریت ساختار ←</span>
      </Link>

      <ProductRemovalManager />

      <Link href={"/" + locale + "/admin-panel/media"} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-primary/30 bg-primary/5 p-5 transition hover:bg-primary/10">
        <div><h2 className="font-bold">کتابخانه رسانه</h2><p className="mt-1 text-sm text-muted-foreground">جستجو و مشاهده یکپارچه تصاویر محصولات و بنرهای صفحه اصلی</p></div>
        <span className="shrink-0 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground">ورود به کتابخانه ←</span>
      </Link>

      <Link href={"/" + locale + "/admin-panel/homepage/banners"} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 transition hover:bg-muted">
        <div><h2 className="font-bold">مدیریت بنرهای صفحه اصلی</h2><p className="mt-1 text-sm text-muted-foreground">آپلود تصویر دسکتاپ و موبایل، متن، دکمه و زمان‌بندی نمایش بنرها</p></div>
        <span className="shrink-0 rounded-xl border border-border px-4 py-2.5 text-sm font-semibold">مدیریت بنرها ←</span>
      </Link>

      <Link href={"/" + locale + "/admin-panel/storefront/theme"} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 transition hover:bg-muted">
        <div><h2 className="font-bold">شخصی‌سازی ظاهر فروشگاه</h2><p className="mt-1 text-sm text-muted-foreground">قالب‌های رنگ، فونت، گردی اجزا و حرکت‌های رابط کاربری</p></div>
        <span className="shrink-0 rounded-xl border border-border px-4 py-2.5 text-sm font-semibold">تنظیم ظاهر ←</span>
      </Link>


      <Link href={"/" + locale + "/admin-panel/customers"} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 transition hover:bg-muted">
        <div><h2 className="font-bold">مدیریت مشتریان</h2><p className="mt-1 text-sm text-muted-foreground">فهرست حساب‌ها، وضعیت عضویت و خلاصه سفارش‌ها با رعایت حریم خصوصی</p></div>
        <span className="shrink-0 rounded-xl border border-border px-4 py-2.5 text-sm font-semibold">مشاهده مشتریان ←</span>
      </Link>

      <Link href={"/" + locale + "/admin-panel/support"} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 transition hover:bg-muted">
        <div><h2 className="font-bold">پشتیبانی مشتریان</h2><p className="mt-1 text-sm text-muted-foreground">صندوق تیکت‌ها، گفت‌وگو با مشتری و مدیریت وضعیت درخواست‌ها</p></div>
        <span className="shrink-0 rounded-xl border border-border px-4 py-2.5 text-sm font-semibold">ورود به پشتیبانی ←</span>
      </Link>

      <Link href={"/" + locale + "/admin-panel/shipping"} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 transition hover:bg-muted">
        <div><h2 className="font-bold">مدیریت روش‌های ارسال</h2><p className="mt-1 text-sm text-muted-foreground">تعریف شرکت حمل، تعرفه‌ها، محدوده سرویس‌دهی و زمان تحویل</p></div>
        <span className="shrink-0 rounded-xl border border-border px-4 py-2.5 text-sm font-semibold">مدیریت ارسال ←</span>
      </Link>

      <Link href={"/" + locale + "/admin-panel/homepage"} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-primary/30 bg-primary/5 p-5 transition hover:bg-primary/10">
        <div><h2 className="font-bold">مدیریت صفحه اصلی</h2><p className="mt-1 text-sm text-muted-foreground">ساخت و انتشار بخش‌های دسته‌بندی و محصولات منتخب در ویترین فروشگاه</p></div>
        <span className="shrink-0 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground">مدیریت صفحه اصلی ←</span>
      </Link>


      <Link href={"/" + locale + "/admin-panel/staff"} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 transition hover:bg-muted">
        <div><h2 className="font-bold">مدیریت مدیران و نقش‌ها</h2><p className="mt-1 text-sm text-muted-foreground">تعریف نقش‌ها، تعیین مجوزها و تخصیص دسترسی به مدیران</p></div>
        <span className="shrink-0 rounded-xl border border-border px-4 py-2.5 text-sm font-semibold">مدیریت دسترسی‌ها ←</span>
      </Link>

      <Link href={"/" + locale + "/admin-panel/audit-log"} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 transition hover:bg-muted">
        <div><h2 className="font-bold">تاریخچه فعالیت مدیران</h2><p className="mt-1 text-sm text-muted-foreground">مشاهده عملیات مدیریتی، زمان اجرا و نتیجه درخواست‌ها</p></div>
        <span className="shrink-0 rounded-xl border border-border px-4 py-2.5 text-sm font-semibold">مشاهده تاریخچه ←</span>
      </Link>


    </main>
  );
}
