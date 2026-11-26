"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { authApi } from "@/lib/auth/api";
import type { AuthUser } from "@/lib/auth/api";

const workspaceItems = [
  {
    title: "محصول جدید",
    description: "ثبت نام، رنگ، تصاویر، دسته‌بندی، سایزها و موجودی اولیه محصول",
    href: (locale: string) => `/${locale}/admin-panel/catalog?mode=create`,
    icon: "＋",
    featured: true,
  },
  {
    title: "ویرایش محصولات",
    description: "مشاهده کارت محصولات و مدیریت مشخصات، تصاویر، قیمت و موجودی",
    href: (locale: string) => `/${locale}/admin-panel/catalog?mode=edit`,
    icon: "▦",
    featured: false,
  },
  {
    title: "مدیریت دسته‌بندی‌ها",
    description: "افزودن و ویرایش دسته‌بندی‌ها و مشخصات اختصاصی هر دسته",
    href: (locale: string) => `/${locale}/admin-panel/catalog/taxonomy`,
    icon: "◇",
    featured: false,
  },
  {
    title: "سفارش‌های موفق",
    description: "مشاهده سفارش‌هایی که پرداخت آن‌ها با موفقیت تأیید شده است",
    href: (locale: string) => `/${locale}/admin-panel/orders?payment_status=paid`,
    icon: "▤",
    featured: false,
  },
];

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
    return <main dir="rtl" className="mx-auto w-full max-w-5xl px-4 py-16 text-center text-muted-foreground">در حال بررسی دسترسی مدیریت…</main>;
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
    <main dir="rtl" className="mx-auto w-full max-w-5xl px-4 py-8 sm:py-12">
      <header className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">ودزمانی</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">پنل مدیریت</h1>
          <p className="mt-2 text-sm text-muted-foreground">ابزارهای اصلی مدیریت فروشگاه</p>
        </div>
        <div className="text-sm text-muted-foreground">
          مدیر: <span className="font-medium text-foreground" dir="ltr">{user.phone}</span>
        </div>
      </header>

      <section aria-label="بخش‌های اصلی پنل مدیریت" className="mt-7 grid gap-4 sm:grid-cols-2">
        {workspaceItems.map((item) => (
          <Link
            key={item.title}
            href={item.href(locale)}
            className={`group flex min-h-36 items-start gap-4 rounded-2xl border p-5 transition hover:-translate-y-0.5 hover:shadow-sm ${item.featured ? "border-primary/40 bg-primary/5 hover:bg-primary/10" : "border-border bg-card hover:bg-muted/50"}`}
          >
            <span aria-hidden="true" className={`flex size-11 shrink-0 items-center justify-center rounded-xl text-xl font-bold ${item.featured ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"}`}>
              {item.icon}
            </span>
            <span className="min-w-0">
              <strong className="block text-base">{item.title}</strong>
              <span className="mt-2 block text-sm leading-7 text-muted-foreground">{item.description}</span>
              <span className="mt-3 block text-xs font-semibold text-primary">ورود به بخش ←</span>
            </span>
          </Link>
        ))}
      </section>

      <footer className="mt-8 rounded-2xl border border-dashed border-border bg-muted/30 px-5 py-4 text-center">
        <p className="font-semibold">سایر امکانات پنل در حال توسعه است</p>
        <p className="mt-1 text-xs leading-6 text-muted-foreground">بخش‌های بیشتری به‌مرور و پس از تکمیل امکانات اصلی اضافه خواهند شد.</p>
      </footer>
    </main>
  );
}
