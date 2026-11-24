"use client";

import Link from "next/link";
import { createContext, useContext, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { authApi } from "@/lib/auth/api";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type ContextValue = { enabled: boolean; locale: string };
type EditableSection = { id: number; title: string; eyebrow: string; show_view_all: boolean; view_all_url: string };
const AdminStorefrontContext = createContext<ContextValue>({ enabled: false, locale: "fa" });

function errorMessage(error: unknown): string {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "حساب شما مجوز ویرایش این بخش را ندارد.";
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "ذخیره تغییرات انجام نشد. اطلاعات را بررسی و دوباره تلاش کنید.";
}

export function AdminStorefrontMode({ locale, children }: { locale: string; children: ReactNode }) {
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("admin") !== "1") return;
    let active = true;
    authApi.me().then((user) => {
      if (active) setAuthorized(user?.is_staff === true);
    }).catch(() => {
      if (active) setAuthorized(false);
    });
    return () => { active = false; };
  }, []);

  const enabled = authorized;
  return (
    <AdminStorefrontContext.Provider value={{ enabled, locale }}>
      {enabled && (
        <div className="sticky top-0 z-50 border-b border-primary/30 bg-primary text-primary-foreground shadow-sm">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div>
              <p className="text-sm font-bold">حالت مدیریت فروشگاه فعال است</p>
              <p className="mt-0.5 text-xs opacity-80">برای ویرایش هر بخش از کنترل همان بخش استفاده کنید.</p>
            </div>
            <nav aria-label="ابزارهای مدیریت فروشگاه" className="flex flex-wrap items-center gap-2 text-xs font-semibold sm:text-sm">
              <Link href={"/" + locale + "/admin-panel/homepage?new=1"} className="rounded-lg bg-primary-foreground px-3 py-2 text-primary hover:opacity-90">افزودن بخش</Link>
              <Link href={"/" + locale + "/admin-panel/homepage"} className="rounded-lg border border-primary-foreground/40 px-3 py-2 hover:bg-primary-foreground/10">مدیریت صفحه اصلی</Link>
              <Link href={"/" + locale + "/admin-panel/homepage/banners"} className="rounded-lg border border-primary-foreground/40 px-3 py-2 hover:bg-primary-foreground/10">مدیریت بنرها</Link>
              <Link href={"/" + locale} className="rounded-lg border border-primary-foreground/40 px-3 py-2 hover:bg-primary-foreground/10">خروج از حالت مدیریت</Link>
            </nav>
          </div>
        </div>
      )}
      {children}
    </AdminStorefrontContext.Provider>
  );
}

export function AdminStorefrontSection({ section, children }: { section: EditableSection; children: ReactNode }) {
  const { enabled, locale } = useContext(AdminStorefrontContext);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(section.title);
  const [eyebrow, setEyebrow] = useState(section.eyebrow);
  const [showViewAll, setShowViewAll] = useState(section.show_view_all);
  const [viewAllUrl, setViewAllUrl] = useState(section.view_all_url);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedTitle = title.trim();
    const trimmedUrl = viewAllUrl.trim();
    if (!trimmedTitle) { setError("عنوان بخش را وارد کنید."); return; }
    if (showViewAll && trimmedUrl && (!trimmedUrl.startsWith("/") || trimmedUrl.startsWith("//"))) {
      setError("لینک باید یک مسیر داخلی مانند /products باشد.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiRequest("PATCH", "/api/admin/homepage/sections/" + section.id + "/", {
        title: trimmedTitle,
        eyebrow: eyebrow.trim(),
        show_view_all: showViewAll,
        view_all_url: showViewAll ? trimmedUrl : "",
      });
      window.location.reload();
    } catch (reason) {
      setError(errorMessage(reason));
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm("این بخش و تاریخچه نسخه‌های آن حذف شود؟ این کار قابل بازگردانی نیست.")) return;
    setSaving(true);
    setError("");
    try {
      await apiRequest("DELETE", "/api/admin/homepage/sections/" + section.id + "/");
      window.location.reload();
    } catch (reason) {
      setError(errorMessage(reason));
      setSaving(false);
    }
  }

  if (!enabled) return <>{children}</>;
  return (
    <div className="relative">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-end gap-2 px-4 pt-3">
        <span className="me-auto text-xs font-medium text-primary">بخش قابل مدیریت · {section.title}</span>
        <button type="button" onClick={() => { setEditing((value) => !value); setError(""); }} className="rounded-lg border border-primary/40 bg-primary/5 px-3 py-2 text-xs font-semibold text-foreground hover:bg-primary/10">
          {editing ? "بستن ویرایش" : "ویرایش همین بخش"}
        </button>
        <Link href={"/" + locale + "/admin-panel/homepage?edit=" + section.id} className="rounded-lg border border-border px-3 py-2 text-xs font-semibold hover:bg-muted">تنظیمات کامل</Link>
        <button type="button" disabled={saving} onClick={() => void remove()} className="rounded-lg border border-destructive/40 px-3 py-2 text-xs font-semibold text-destructive hover:bg-destructive/5 disabled:opacity-50">حذف بخش</button>
      </div>
      {editing && (
        <form onSubmit={save} className="mx-4 mt-3 rounded-2xl border border-primary/30 bg-card p-4 shadow-sm sm:mx-auto sm:max-w-6xl sm:p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium">عنوان بخش<input value={title} maxLength={120} onChange={(event) => setTitle(event.target.value)} className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm" /></label>
            <label className="block text-sm font-medium">متن بالای عنوان<input value={eyebrow} maxLength={120} onChange={(event) => setEyebrow(event.target.value)} className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm" /></label>
          </div>
          <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={showViewAll} onChange={(event) => setShowViewAll(event.target.checked)} />نمایش پیوند «مشاهده همه»</label>
          {showViewAll && <label className="mt-3 block text-sm font-medium">مسیر داخلی پیوند<input dir="ltr" value={viewAllUrl} onChange={(event) => setViewAllUrl(event.target.value)} placeholder="/products" className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm" /></label>}
          {error && <p role="alert" className="mt-3 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</p>}
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="submit" disabled={saving || !title.trim()} className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50">{saving ? "در حال ذخیره…" : "ذخیره تغییرات روی فروشگاه"}</button>
            <button type="button" disabled={saving} onClick={() => { setTitle(section.title); setEyebrow(section.eyebrow); setShowViewAll(section.show_view_all); setViewAllUrl(section.view_all_url); setEditing(false); setError(""); }} className="rounded-xl border border-border px-4 py-2.5 text-sm hover:bg-muted">انصراف</button>
          </div>
        </form>
      )}
      {children}
    </div>
  );
}
