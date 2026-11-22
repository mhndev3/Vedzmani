"use client";

import { useEffect, useState, type FormEvent } from "react";
import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type MediaItem = {
  id: string;
  source: "product" | "banner";
  source_id: number;
  source_label: string;
  title: string;
  alt_text: string;
  url: string;
  thumbnail_url: string;
  width: number | null;
  height: number | null;
  file_size: number | null;
  created_at: string;
  owner_label: string;
  owner_url: string;
};
type MediaPage = { count: number; next: string | null; previous: string | null; results: MediaItem[] };

const secondary = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";

function errorMessage(error: unknown) {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) {
    return "مجوز مشاهده کتابخانه رسانه برای حساب شما فعال نیست.";
  }
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "دریافت کتابخانه رسانه انجام نشد. فیلترها را بررسی کنید.";
}

function formatBytes(value: number | null) {
  if (!value || value <= 0) return "حجم نامشخص";
  return value >= 1024 * 1024
    ? (value / (1024 * 1024)).toLocaleString("fa-IR", { maximumFractionDigits: 1 }) + " مگابایت"
    : Math.ceil(value / 1024).toLocaleString("fa-IR") + " کیلوبایت";
}

export default function AdminMediaLibraryPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [items, setItems] = useState<MediaItem[]>([]);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [source, setSource] = useState<"all" | "product" | "banner">("all");
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      setError("");
      const search = new URLSearchParams({ page: String(page), source });
      if (appliedQuery) search.set("q", appliedQuery);
      try {
        const result = await apiRequest<MediaPage>("GET", `/api/admin/media/?${search.toString()}`);
        if (!active) return;
        setItems(result.results);
        setCount(result.count);
      } catch (e) {
        if (!active) return;
        setError(errorMessage(e));
        setItems([]);
        setCount(0);
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => { active = false; };
  }, [page, source, appliedQuery]);

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    if (value.length === 1) {
      setError("برای جستجو حداقل دو نویسه وارد کنید.");
      return;
    }
    if (value !== appliedQuery || page !== 1) setLoading(true);
    setPage(1);
    setAppliedQuery(value);
  }

  function changeSource(value: "all" | "product" | "banner") {
    if (value === source) return;
    setLoading(true);
    setSource(value);
    setPage(1);
  }

  const pageSize = 24;
  const pageCount = Math.max(1, Math.ceil(count / pageSize));

  return <main dir="rtl" className="mx-auto w-full max-w-7xl px-4 py-8 sm:py-10">
    <div className="mb-7">
      <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
      <h1 className="mt-3 text-2xl font-bold sm:text-3xl">کتابخانه رسانه</h1>
      <p className="mt-2 max-w-3xl text-sm leading-7 text-muted-foreground">
        تصاویر ثبت‌شده محصولات و بنرهای صفحه اصلی را یک‌جا جستجو و بررسی کنید. برای تغییر یا بارگذاری تصویر، به بخش مربوط به همان محصول یا بنر بروید؛ فایل‌های اصلی از این صفحه حذف یا جابه‌جا نمی‌شوند.
      </p>
    </div>

    <section className="rounded-2xl border border-border bg-card p-4 sm:p-5">
      <form onSubmit={search} className="flex flex-col gap-3 sm:flex-row">
        <input value={query} onChange={event => setQuery(event.target.value)} maxLength={100}
          placeholder="جستجو بر اساس نام محصول، رنگ، عنوان بنر یا متن جایگزین…"
          className="min-w-0 flex-1 rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary" />
        <button type="submit" className="rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground">جستجو</button>
        <button type="button" className={secondary} onClick={() => { if (query || appliedQuery || page !== 1) setLoading(true); setQuery(""); setAppliedQuery(""); setPage(1); }}>پاک‌کردن جستجو</button>
      </form>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="ml-1 text-xs text-muted-foreground">نوع رسانه:</span>
        <button type="button" aria-pressed={source === "all"} onClick={() => changeSource("all")} className={source === "all" ? "rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground" : secondary}>همه</button>
        <button type="button" aria-pressed={source === "product"} onClick={() => changeSource("product")} className={source === "product" ? "rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground" : secondary}>تصاویر محصولات</button>
        <button type="button" aria-pressed={source === "banner"} onClick={() => changeSource("banner")} className={source === "banner" ? "rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground" : secondary}>تصاویر بنرها</button>
        <span className="mr-auto text-xs text-muted-foreground">{count.toLocaleString("fa-IR")} فایل</span>
      </div>
    </section>

    {error && <p role="alert" className="mt-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</p>}

    {loading ? <p className="py-16 text-center text-sm text-muted-foreground">در حال دریافت رسانه‌ها…</p> :
      items.length === 0 ? <div className="mt-6 rounded-2xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">رسانه‌ای با این فیلترها پیدا نشد.</div> :
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {items.map(item => <article key={item.id} className="overflow-hidden rounded-2xl border border-border bg-card">
            <div className="relative aspect-[4/5] bg-muted">
              <Image src={item.thumbnail_url || item.url} alt={item.alt_text || item.title} fill sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw" unoptimized className="object-cover" />
              <span className="absolute right-2 top-2 rounded-full bg-background/90 px-2 py-1 text-[10px] font-semibold">{item.source_label}</span>
            </div>
            <div className="space-y-2 p-3">
              <h2 className="line-clamp-1 text-sm font-semibold" title={item.title}>{item.title}</h2>
              <p className="line-clamp-1 text-xs text-muted-foreground" title={item.alt_text}>{item.alt_text || "بدون متن جایگزین"}</p>
              <p className="text-[11px] text-muted-foreground">
                {item.width && item.height ? `${item.width} × ${item.height} پیکسل · ` : ""}
                {formatBytes(item.file_size)}
              </p>
              <p className="line-clamp-1 text-[11px] text-muted-foreground">{new Date(item.created_at).toLocaleDateString("fa-IR")}</p>
              <Link href={`/${locale}${item.owner_url}`} className="inline-flex rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-muted">
                مدیریت منبع تصویر
              </Link>
            </div>
          </article>)}
        </div>}

    {!loading && count > 0 && <div className="mt-6 flex items-center justify-between gap-3 rounded-xl border border-border p-3">
      <button type="button" disabled={page <= 1} onClick={() => { setLoading(true); setPage(value => Math.max(1, value - 1)); }} className={secondary}>صفحه قبل</button>
      <span className="text-xs text-muted-foreground">صفحه {page.toLocaleString("fa-IR")} از {pageCount.toLocaleString("fa-IR")}</span>
      <button type="button" disabled={page >= pageCount} onClick={() => { setLoading(true); setPage(value => Math.min(pageCount, value + 1)); }} className={secondary}>صفحه بعد</button>
    </div>}
  </main>;
}
