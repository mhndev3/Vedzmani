"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";

type NavItem = { label: string; path: string; exact?: boolean };
type NavGroup = { title: string; items: NavItem[] };

const groups: NavGroup[] = [
  {
    title: "نمای کلی",
    items: [{ label: "داشبورد مدیریت", path: "" , exact: true }],
  },
  {
    title: "محصولات و انبار",
    items: [
      { label: "محصولات و موجودی", path: "/catalog" },
      { label: "دسته‌بندی‌ها و مجموعه‌ها", path: "/catalog/taxonomy" },
      { label: "کتابخانه تصاویر", path: "/media" },
    ],
  },
  {
    title: "ویترین فروشگاه",
    items: [
      { label: "بخش‌های صفحه اصلی", path: "/homepage" },
      { label: "بنرهای تبلیغاتی", path: "/homepage/banners" },
      { label: "قالب و ظاهر فروشگاه", path: "/storefront/theme" },
    ],
  },
  {
    title: "مشتریان و ارتباط",
    items: [
      { label: "مشتریان", path: "/customers" },
      { label: "سفارش‌ها", path: "/orders" },
      { label: "پشتیبانی مشتریان", path: "/support" },
      { label: "روش‌های ارسال", path: "/shipping" },
    ],
  },
  {
    title: "مدیریت و امنیت",
    items: [
      { label: "مدیران و سطح دسترسی", path: "/staff" },
      { label: "گزارش فعالیت مدیران", path: "/audit-log" },
    ],
  },
];

function isActive(pathname: string, href: string, exact?: boolean) {
  return exact ? pathname === href : pathname === href || pathname.startsWith(href + "/");
}

export default function AdminPanelLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const pathname = usePathname();
  const root = "/" + locale + "/admin-panel";

  return (
    <div dir="rtl" className="mx-auto w-full max-w-[1500px] px-3 pb-8 sm:px-5 lg:px-7">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card px-4 py-3 sm:px-5">
        <div>
          <p className="text-xs font-medium text-muted-foreground">فضای اختصاصی مدیریت</p>
          <p className="mt-1 text-base font-bold">مدیریت فروشگاه ودزمانی</p>
        </div>
        <Link href={"/" + locale} className="inline-flex items-center gap-2 rounded-xl border border-border bg-background px-3 py-2 text-sm font-medium transition hover:bg-muted">
          <span aria-hidden="true">↗</span>
          بازگشت به فروشگاه
        </Link>
      </div>

      <div className="grid min-w-0 gap-5 lg:grid-cols-[248px_minmax(0,1fr)] lg:items-start">
        <aside className="min-w-0 rounded-2xl border border-border bg-card p-3 lg:sticky lg:top-24">
          <div className="mb-3 flex items-center justify-between px-2 py-2">
            <span className="text-sm font-bold">منوی مدیریت</span>
            <span className="rounded-full bg-muted px-2 py-1 text-[11px] text-muted-foreground">مدیریت</span>
          </div>

          <nav aria-label="منوی پنل مدیریت" className="hidden space-y-4 lg:block">
            {groups.map((group) => (
              <section key={group.title}>
                <h2 className="mb-1 px-3 text-[11px] font-semibold text-muted-foreground">{group.title}</h2>
                <div className="space-y-1">
                  {group.items.map((item) => {
                    const href = root + item.path;
                    const active = isActive(pathname, href, item.exact);
                    return (
                      <Link
                        key={href}
                        href={href}
                        prefetch={false}
                        aria-current={active ? "page" : undefined}
                        className={"flex min-h-10 items-center justify-between rounded-xl px-3 py-2 text-sm transition-colors " + (active ? "bg-primary text-primary-foreground font-semibold" : "text-foreground hover:bg-muted")}
                      >
                        <span>{item.label}</span>
                        {active ? <span aria-hidden="true" className="text-xs">●</span> : null}
                      </Link>
                    );
                  })}
                </div>
              </section>
            ))}
          </nav>

          <nav aria-label="دسترسی سریع پنل مدیریت" className="flex gap-2 overflow-x-auto pb-1 lg:hidden">
            {groups.flatMap((group) => group.items).map((item) => {
              const href = root + item.path;
              const active = isActive(pathname, href, item.exact);
              return (
                <Link
                  key={href}
                  href={href}
                  prefetch={false}
                  aria-current={active ? "page" : undefined}
                  className={"shrink-0 whitespace-nowrap rounded-xl border px-3 py-2 text-xs font-medium transition-colors " + (active ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background hover:bg-muted")}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <div className="min-w-0 rounded-2xl border border-border bg-background">
          {children}
        </div>
      </div>
    </div>
  );
}
