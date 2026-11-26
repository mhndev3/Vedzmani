"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Category = { id: number; name: string; slug: string; is_active: boolean; position: number };
type Page<T> = { results: T[]; next: string | null };

const inputClass = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none focus:border-primary";
const primaryClass = "rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondaryClass = "rounded-xl border border-border px-3 py-2 text-sm text-foreground hover:bg-muted disabled:opacity-50";

async function getAllCategories(): Promise<Category[]> {
  const rows: Category[] = [];
  let next: string | null = "/api/admin/catalog/categories/";
  const visited = new Set<string>();
  while (next) {
    if (visited.has(next) || visited.size >= 10000) throw new Error("Category pagination did not terminate.");
    visited.add(next);
    const page: Page<Category> = await apiRequest<Page<Category>>("GET", next);
    rows.push(...page.results);
    next = page.next ? new URL(page.next, window.location.origin).pathname + new URL(page.next, window.location.origin).search : null;
  }
  return rows.sort((a, b) => a.position - b.position || a.id - b.id);
}

function errorMessage(error: unknown) {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "دسترسی مدیریت دسته‌بندی‌ها برای حساب شما فعال نیست.";
  if (error instanceof BrowserApiError && error.status === 400) return "نام دسته‌بندی معتبر نیست یا تکراری است.";
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "ذخیره اطلاعات انجام نشد. دوباره تلاش کنید.";
}

export default function AdminTaxonomyPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState("");
  const [name, setName] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    setCategories(await getAllCategories());
  }, []);

  useEffect(() => {
    let active = true;
    void getAllCategories().then(rows => { if (active) setCategories(rows); })
      .catch(cause => { if (active) setError(errorMessage(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const visibleCategories = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    return categories.filter(category => !term || category.name.toLocaleLowerCase().includes(term));
  }, [categories, search]);

  function startEdit(category: Category) {
    setEditingId(category.id);
    setName(category.name);
    setError("");
    setNotice("");
  }

  function cancelEdit() {
    setEditingId(null);
    setName("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanName = name.trim();
    if (!cleanName) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      if (editingId !== null) {
        await apiRequest("PATCH", `/api/admin/catalog/categories/${editingId}/`, { name: cleanName });
        setNotice("نام دسته‌بندی به‌روزرسانی شد.");
      } else {
        // Slugs are internal routing identifiers. Generate them automatically instead of asking the manager to invent one.
        await apiRequest("POST", "/api/admin/catalog/categories/", {
          name: cleanName,
          slug: `category-${Date.now().toString(36)}`,
          position: categories.length,
          is_active: true,
          product_fields: [],
          size_ids: [],
        });
        setNotice("دسته‌بندی اصلی جدید اضافه شد.");
      }
      cancelEdit();
      await refresh();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(category: Category) {
    const action = category.is_active ? "از فهرست دسته‌بندی‌های فعال خارج شود؟ محصولات و اطلاعات آن حذف نمی‌شوند." : "دسته‌بندی دوباره فعال شود؟";
    if (!window.confirm(action)) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await apiRequest("PATCH", `/api/admin/catalog/categories/${category.id}/`, { is_active: !category.is_active });
      await refresh();
      setNotice(category.is_active ? "دسته‌بندی غیرفعال شد؛ محصولات و سوابق حفظ شدند." : "دسته‌بندی دوباره فعال شد.");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  async function move(category: Category, delta: number) {
    const ordered = [...categories];
    const index = ordered.findIndex(item => item.id === category.id);
    const target = index + delta;
    if (target < 0 || target >= ordered.length) return;
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await apiRequest("POST", "/api/admin/catalog/categories/reorder/", { entry_ids: ordered.map(item => item.id) });
      await refresh();
      setNotice("ترتیب دسته‌بندی‌ها ذخیره شد.");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <main dir="rtl" className="admin-panel mx-auto w-full max-w-5xl px-4 py-8 sm:py-10">
      <div className="mb-7">
        <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
        <h1 className="mt-3 text-2xl font-bold sm:text-3xl text-foreground">مدیریت دسته‌بندی‌های اصلی</h1>
        <p className="mt-2 text-sm leading-7 text-muted-foreground">دسته‌های اصلی فروشگاه مثل دورس، بافت، هودی و اکسسوری را اضافه و مدیریت کنید. شناسه فنی هر دسته به‌صورت خودکار ساخته می‌شود.</p>
      </div>

      {notice && <p role="status" className="mb-4 rounded-xl border border-border bg-muted p-3 text-sm text-foreground">{notice}</p>}
      {error && <p role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}

      <section className="rounded-2xl border border-border bg-card p-5 sm:p-6">
        <h2 className="font-bold text-foreground">{editingId === null ? "افزودن دسته‌بندی اصلی" : "ویرایش نام دسته‌بندی"}</h2>
        <form onSubmit={save} className="mt-4 flex flex-col gap-3 sm:flex-row">
          <label className="min-w-0 flex-1 text-sm font-medium text-foreground">
            نام دسته‌بندی
            <input required maxLength={100} value={name} onChange={event => setName(event.target.value)} className={inputClass} placeholder="مثلاً اکسسوری" />
          </label>
          <div className="flex items-end gap-2">
            <button type="submit" disabled={saving || !name.trim()} className={primaryClass}>{saving ? "در حال ذخیره…" : editingId === null ? "افزودن دسته" : "ذخیره نام"}</button>
            {editingId !== null && <button type="button" disabled={saving} onClick={cancelEdit} className={secondaryClass}>انصراف</button>}
          </div>
        </form>
      </section>

      <section className="mt-6 rounded-2xl border border-border bg-card p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="font-bold text-foreground">دسته‌بندی‌های فروشگاه</h2><p className="mt-1 text-xs text-muted-foreground">{categories.length.toLocaleString("fa-IR")} دسته‌بندی</p></div>
          <input value={search} onChange={event => setSearch(event.target.value)} placeholder="جستجوی دسته‌بندی…" aria-label="جستجوی دسته‌بندی" className={inputClass + " sm:max-w-xs"} />
        </div>
        {loading ? <p className="py-10 text-center text-sm text-muted-foreground">در حال دریافت دسته‌بندی‌ها…</p> : visibleCategories.length === 0 ? <p className="rounded-xl border border-dashed border-border py-10 text-center text-sm text-muted-foreground">دسته‌بندی‌ای پیدا نشد.</p> : (
          <div className="divide-y divide-border">
            {visibleCategories.map(category => {
              const index = categories.findIndex(item => item.id === category.id);
              return <article key={category.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                <div className="min-w-0">
                  <h3 className="font-semibold text-foreground">{category.name}</h3>
                  <p className="mt-1 text-xs text-muted-foreground">{category.is_active ? "فعال در فروشگاه" : "غیرفعال"} · جایگاه {category.position + 1}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" disabled={saving || index === 0} onClick={() => void move(category, -1)} className={secondaryClass}>بالا</button>
                  <button type="button" disabled={saving || index === categories.length - 1} onClick={() => void move(category, 1)} className={secondaryClass}>پایین</button>
                  <button type="button" disabled={saving} onClick={() => startEdit(category)} className={secondaryClass}>ویرایش نام</button>
                  <button type="button" disabled={saving} onClick={() => void toggleActive(category)} className={secondaryClass}>{category.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}</button>
                </div>
              </article>;
            })}
          </div>
        )}
      </section>
    </main>
  );
}
