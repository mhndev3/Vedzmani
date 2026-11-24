"use client";

import Link from "next/link";
import { createContext, useContext, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { authApi } from "@/lib/auth/api";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type ContextValue = { enabled: boolean; locale: string };
type SectionType = "categories" | "products" | "newest_products";
type EditableSection = {
  id: number;
  position: number;
  title: string;
  eyebrow: string;
  section_type: SectionType;
  show_view_all: boolean;
  view_all_url: string;
  category_ids: number[];
  product_ids: number[];
};
type CatalogEntry = { id: number; name: string; slug?: string; product_code?: string | null; is_active: boolean };
type CatalogPage = { results: CatalogEntry[]; next: string | null };
const AdminStorefrontContext = createContext<ContextValue>({ enabled: false, locale: "fa" });

function errorMessage(error: unknown): string {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "حساب شما مجوز ویرایش این بخش را ندارد.";
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "ذخیره تغییرات انجام نشد. اطلاعات را بررسی و دوباره تلاش کنید.";
}

async function getAllEntries(path: string): Promise<CatalogEntry[]> {
  const rows: CatalogEntry[] = [];
  let next: string | null = path;
  let pages = 0;
  while (next && pages < 100) {
    const page = await apiRequest<CatalogPage>("GET", next);
    rows.push(...page.results);
    next = page.next
      ? new URL(page.next, window.location.origin).pathname + new URL(page.next, window.location.origin).search
      : null;
    pages += 1;
  }
  return rows;
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
  const [itemsOpen, setItemsOpen] = useState(false);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [itemsSaving, setItemsSaving] = useState(false);
  const [itemsError, setItemsError] = useState("");
  const [itemsNotice, setItemsNotice] = useState("");
  const [itemSearch, setItemSearch] = useState("");
  const [itemOptions, setItemOptions] = useState<CatalogEntry[]>([]);
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<number[]>(section.category_ids);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>(section.product_ids);

  async function toggleItems() {
    if (itemsOpen) {
      setItemsOpen(false);
      return;
    }
    setItemsOpen(true);
    setItemsLoading(true);
    setItemsError("");
    setItemsNotice("");
    setItemSearch("");
    setSelectedCategoryIds(section.category_ids);
    setSelectedProductIds(section.product_ids);
    try {
      const endpoint = section.section_type === "categories"
        ? "/api/admin/catalog/categories/"
        : "/api/admin/catalog/products/";
      const rows = await getAllEntries(endpoint);
      setItemOptions(rows.filter(item => item.is_active));
    } catch (reason) {
      setItemsError(errorMessage(reason));
      setItemOptions([]);
    } finally {
      setItemsLoading(false);
    }
  }

  function toggleItem(id: number) {
    if (section.section_type === "categories") {
      setSelectedCategoryIds(current => current.includes(id)
        ? current.filter(value => value !== id)
        : [...current, id]);
    } else {
      setSelectedProductIds(current => current.includes(id)
        ? current.filter(value => value !== id)
        : [...current, id]);
    }
  }

  async function saveItems() {
    setItemsSaving(true);
    setItemsError("");
    setItemsNotice("");
    try {
      const payload = section.section_type === "categories"
        ? { categories: selectedCategoryIds }
        : { products: selectedProductIds };
      await apiRequest("PATCH", `/api/admin/homepage/sections/${section.id}/`, payload);
      window.location.reload();
    } catch (reason) {
      setItemsError(errorMessage(reason));
      setItemsSaving(false);
    }
  }

  const filteredItems = itemOptions.filter(item => {
    const query = itemSearch.trim().toLocaleLowerCase();
    return !query || item.name.toLocaleLowerCase().includes(query)
      || String(item.id).includes(query)
      || String(item.product_code ?? "").toLocaleLowerCase().includes(query);
  });

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
        <Link
          href={"/" + locale + "/admin-panel/homepage?new=1&position=" + (section.position + 1)}
          className="rounded-lg border border-primary/40 bg-primary/5 px-3 py-2 text-xs font-semibold text-foreground hover:bg-primary/10"
        >＋ افزودن بخش در اینجا</Link>
        <button type="button" onClick={() => { setEditing((value) => !value); setError(""); }} className="rounded-lg border border-primary/40 bg-primary/5 px-3 py-2 text-xs font-semibold text-foreground hover:bg-primary/10">
          {editing ? "بستن ویرایش" : "ویرایش همین بخش"}
        </button>
        {section.section_type !== "newest_products" || section.product_ids.length > 0 ? (
          <button type="button" onClick={() => void toggleItems()} className="rounded-lg border border-border px-3 py-2 text-xs font-semibold hover:bg-muted">
            {itemsOpen ? "بستن مدیریت کارت‌ها" : section.section_type === "categories" ? "مدیریت کارت‌های دسته‌بندی" : "افزودن کارت محصول"}
          </button>
        ) : (
          <button type="button" onClick={() => void toggleItems()} className="rounded-lg border border-border px-3 py-2 text-xs font-semibold hover:bg-muted">＋ افزودن کارت محصول</button>
        )}
        <Link href={"/" + locale + "/admin-panel/homepage?edit=" + section.id} className="rounded-lg border border-border px-3 py-2 text-xs font-semibold hover:bg-muted">تنظیمات کامل</Link>
        <button type="button" disabled={saving} onClick={() => void remove()} className="rounded-lg border border-destructive/40 px-3 py-2 text-xs font-semibold text-destructive hover:bg-destructive/5 disabled:opacity-50">حذف بخش</button>
      </div>
      {itemsOpen && (
        <section className="mx-4 mt-3 rounded-2xl border border-primary/30 bg-card p-4 shadow-sm sm:mx-auto sm:max-w-6xl sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold">{section.section_type === "categories" ? "مدیریت کارت‌های دسته‌بندی" : "افزودن کارت محصول به این بخش"}</h3>
              <p className="mt-1 text-xs leading-6 text-muted-foreground">
                {section.section_type === "categories"
                  ? "دسته‌بندی‌های انتخاب‌شده در همین بخش نمایش داده می‌شوند."
                  : section.section_type === "newest_products"
                    ? "محصولات انتخاب‌شده ابتدا نمایش داده می‌شوند و ظرفیت باقی‌مانده با جدیدترین محصولات تکمیل می‌شود."
                    : "محصولات فعال موردنظر را برای نمایش در این بخش انتخاب کنید."}
              </p>
            </div>
            <span className="rounded-full bg-muted px-3 py-1 text-xs">
              {section.section_type === "categories" ? selectedCategoryIds.length : selectedProductIds.length} مورد انتخاب‌شده
            </span>
          </div>
          <input
            value={itemSearch}
            onChange={event => setItemSearch(event.target.value)}
            placeholder={section.section_type === "categories" ? "جستجوی دسته‌بندی…" : "جستجوی محصول با نام یا کد…"}
            className="mt-4 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm"
          />
          {itemsError && <p role="alert" className="mt-3 rounded-lg border border-destructive/40 p-3 text-sm text-destructive">{itemsError}</p>}
          {itemsNotice && <p role="status" className="mt-3 rounded-lg bg-muted p-3 text-sm">{itemsNotice}</p>}
          {itemsLoading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">در حال دریافت موارد قابل انتخاب…</p>
          ) : (
            <div className="mt-3 max-h-64 space-y-2 overflow-y-auto rounded-xl border border-border p-3">
              {filteredItems.length === 0 ? (
                <p className="py-5 text-center text-sm text-muted-foreground">موردی با این جستجو پیدا نشد.</p>
              ) : filteredItems.map(item => {
                const checked = section.section_type === "categories"
                  ? selectedCategoryIds.includes(item.id)
                  : selectedProductIds.includes(item.id);
                return (
                  <label key={item.id} className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-sm hover:bg-muted/60">
                    <input type="checkbox" checked={checked} disabled={itemsSaving} onChange={() => toggleItem(item.id)} />
                    <span className="min-w-0 flex-1 truncate">{item.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{item.product_code ? `کد ${item.product_code}` : `#${item.id}`}</span>
                  </label>
                );
              })}
            </div>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" disabled={itemsLoading || itemsSaving || (section.section_type === "categories" ? selectedCategoryIds.length === 0 : selectedProductIds.length === 0)} onClick={() => void saveItems()} className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50">
              {itemsSaving ? "در حال ذخیره…" : "ذخیره کارت‌های این بخش"}
            </button>
            <button type="button" disabled={itemsSaving} onClick={() => { setItemsOpen(false); setItemsError(""); }} className="rounded-xl border border-border px-4 py-2.5 text-sm hover:bg-muted">انصراف</button>
          </div>
        </section>
      )}
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
