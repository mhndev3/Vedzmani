"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type CatalogGroup = "categories" | "collections";
type Entry = { id: number; name: string; slug: string; is_active: boolean; position: number };
type Page<T> = { results: T[]; next: string | null };

const inputClass = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary";
const primaryClass = "rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondaryClass = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";

async function getAll(path: string): Promise<Entry[]> {
  const rows: Entry[] = [];
  let next: string | null = path;
  let pages = 0;
  while (next && pages < 40) {
    const pageData: Page<Entry> = await apiRequest<Page<Entry>>("GET", next);
    rows.push(...pageData.results);
    next = pageData.next
      ? new URL(pageData.next, window.location.origin).pathname + new URL(pageData.next, window.location.origin).search
      : null;
    pages += 1;
  }
  return rows;
}

function errorMessage(error: unknown): string {
  if (error instanceof BrowserApiError) {
    if (error.status === 401 || error.status === 403) return "دسترسی کافی ندارید؛ مجوزهای مشاهده و ویرایش مدل را بررسی کنید.";
    if (error.status === 400) return "نام یا شناسه واردشده معتبر نیست یا قبلاً استفاده شده است.";
    if (error.status === 0) return "ارتباط با سرور برقرار نشد.";
  }
  return "ذخیره اطلاعات انجام نشد. ورودی‌ها را بررسی و دوباره تلاش کنید.";
}

export default function AdminTaxonomyPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [group, setGroup] = useState<CatalogGroup>("categories");
  const [categories, setCategories] = useState<Entry[]>([]);
  const [collections, setCollections] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const endpoint = group === "categories" ? "/api/admin/catalog/categories/" : "/api/admin/catalog/collections/";
  const entries = group === "categories" ? categories : collections;

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [categoryRows, collectionRows] = await Promise.all([
        getAll("/api/admin/catalog/categories/"),
        getAll("/api/admin/catalog/collections/"),
      ]);
      setCategories(categoryRows);
      setCollections(collectionRows);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [categoryRows, collectionRows] = await Promise.all([
          getAll("/api/admin/catalog/categories/"),
          getAll("/api/admin/catalog/collections/"),
        ]);
        if (!cancelled) {
          setCategories(categoryRows);
          setCollections(collectionRows);
        }
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  const visibleEntries = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    return [...entries]
      .sort((a, b) => a.position - b.position || a.id - b.id)
      .filter((entry) => !term || entry.name.toLocaleLowerCase().includes(term) || entry.slug.toLocaleLowerCase().includes(term));
  }, [entries, search]);

  function resetForm(entry?: Entry) {
    setEditing(entry?.id ?? null);
    setName(entry?.name ?? "");
    setSlug(entry?.slug ?? "");
    setError("");
    setNotice("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const payload = { name: name.trim(), slug: slug.trim(), position: editing === null ? entries.length : entries.find((entry) => entry.id === editing)?.position ?? 0 };
      if (editing === null) {
        await apiRequest<Entry>("POST", endpoint, { ...payload, is_active: true });
        setNotice(group === "categories" ? "دسته‌بندی جدید ساخته شد." : "مجموعه جدید ساخته شد.");
      } else {
        await apiRequest<Entry>("PATCH", endpoint + editing + "/", payload);
        setNotice("تغییرات ذخیره شد.");
      }
      resetForm();
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(entry: Entry) {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await apiRequest<Entry>("PATCH", endpoint + entry.id + "/", { is_active: !entry.is_active });
      setNotice(entry.is_active ? "مورد انتخاب‌شده غیرفعال شد؛ سابقه و محصولات مرتبط حفظ شدند." : "مورد دوباره فعال شد.");
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function move(entry: Entry, delta: number) {
    const ordered = [...entries].sort((a, b) => a.position - b.position || a.id - b.id);
    const index = ordered.findIndex((item) => item.id === entry.id);
    const target = index + delta;
    if (target < 0 || target >= ordered.length) return;
    const other = ordered[target];
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await apiRequest<Entry>("PATCH", endpoint + entry.id + "/", { position: other.position });
      await apiRequest<Entry>("PATCH", endpoint + other.id + "/", { position: entry.position });
      setNotice("ترتیب نمایش به‌روزرسانی شد.");
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
      await refresh();
    } finally {
      setSaving(false);
    }
  }

  return (
    <main dir="rtl" className="mx-auto w-full max-w-6xl px-4 py-8 sm:py-10">
      <div className="mb-7">
        <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
        <h1 className="mt-3 text-2xl font-bold sm:text-3xl">مدیریت دسته‌بندی‌ها و مجموعه‌ها</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">ساختار کاتالوگ را مدیریت کنید. غیرفعال‌سازی به‌جای حذف انجام می‌شود تا ارتباط محصولات و سوابق حفظ شود.</p>
      </div>

      <div className="mb-5 flex flex-wrap gap-2" role="tablist" aria-label="نوع گروه کاتالوگ">
        <button type="button" role="tab" aria-selected={group === "categories"} className={group === "categories" ? primaryClass : secondaryClass} onClick={() => { setGroup("categories"); resetForm(); setSearch(""); }}>دسته‌بندی‌ها</button>
        <button type="button" role="tab" aria-selected={group === "collections"} className={group === "collections" ? primaryClass : secondaryClass} onClick={() => { setGroup("collections"); resetForm(); setSearch(""); }}>مجموعه‌ها</button>
      </div>

      {notice && <p role="status" className="mb-4 rounded-xl border border-border bg-muted p-3 text-sm">{notice}</p>}
      {error && <p role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.4fr)]">
        <section className="rounded-2xl border border-border bg-card p-5">
          <h2 className="font-bold">{editing === null ? "افزودن مورد جدید" : "ویرایش مورد"}</h2>
          <form onSubmit={save} className="mt-4 space-y-4">
            <label className="block text-sm">نام فارسی
              <input required maxLength={100} value={name} onChange={(event) => setName(event.target.value)} className={inputClass} />
            </label>
            <label className="block text-sm">شناسه انگلیسی (Slug)
              <input required maxLength={120} pattern="[A-Za-z0-9_-]+" dir="ltr" value={slug} onChange={(event) => setSlug(event.target.value)} className={inputClass} />
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="submit" disabled={saving || !name.trim() || !slug.trim()} className={primaryClass}>{saving ? "در حال ذخیره…" : editing === null ? "ایجاد" : "ذخیره تغییرات"}</button>
              {editing !== null && <button type="button" disabled={saving} className={secondaryClass} onClick={() => resetForm()}>انصراف</button>}
            </div>
          </form>
          <p className="mt-5 text-xs leading-6 text-muted-foreground">شناسه انگلیسی باید یکتا باشد و در نشانی‌ها استفاده می‌شود. حذف فیزیکی در این بخش وجود ندارد.</p>
        </section>

        <section className="min-w-0 rounded-2xl border border-border bg-card p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-bold">{group === "categories" ? "فهرست دسته‌بندی‌ها" : "فهرست مجموعه‌ها"}</h2>
            <span className="text-xs text-muted-foreground">{entries.length.toLocaleString("fa-IR")} مورد</span>
          </div>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="جستجو با نام یا شناسه…" className={inputClass + " my-4"} />
          {loading ? <p className="py-8 text-center text-sm text-muted-foreground">در حال دریافت اطلاعات…</p> :
            visibleEntries.length === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">موردی پیدا نشد.</p> :
              <div className="divide-y divide-border">
                {visibleEntries.map((entry) => {
                  const index = entries.slice().sort((a, b) => a.position - b.position || a.id - b.id).findIndex((item) => item.id === entry.id);
                  return (
                    <article key={entry.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-semibold">{entry.name}</h3>
                          <span className={entry.is_active ? "rounded-full bg-muted px-2 py-1 text-[10px]" : "rounded-full border border-border px-2 py-1 text-[10px] text-muted-foreground"}>{entry.is_active ? "فعال" : "غیرفعال"}</span>
                        </div>
                        <p dir="ltr" className="mt-1 text-left text-xs text-muted-foreground">{entry.slug} · {entry.position}</p>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        <button type="button" className={secondaryClass} disabled={saving || index === 0} onClick={() => void move(entry, -1)} aria-label="انتقال به بالا">↑</button>
                        <button type="button" className={secondaryClass} disabled={saving || index === entries.length - 1} onClick={() => void move(entry, 1)} aria-label="انتقال به پایین">↓</button>
                        <button type="button" className={secondaryClass} disabled={saving} onClick={() => resetForm(entry)}>ویرایش</button>
                        <button type="button" className={secondaryClass} disabled={saving} onClick={() => void toggleActive(entry)}>{entry.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}</button>
                      </div>
                    </article>
                  );
                })}
              </div>}
        </section>
      </div>
    </main>
  );
}
