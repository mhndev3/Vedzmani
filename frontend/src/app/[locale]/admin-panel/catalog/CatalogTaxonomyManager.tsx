"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Row = { id: number; name: string; slug: string; is_active: boolean; position: number };
type Size = { id: number; code: string; label: string; position: number };
type Page<T> = { results: T[]; next: string | null };
const input = "mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm";
const primary = "rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondary = "rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-50";

async function all<T>(path: string): Promise<T[]> {
  const rows: T[] = [];
  let next: string | null = path;
  for (let page = 0; next && page < 40; page += 1) {
    const result = await apiRequest<Page<T>>("GET", next);
    rows.push(...result.results);
    next = result.next ? new URL(result.next, window.location.origin).pathname + new URL(result.next, window.location.origin).search : null;
  }
  return rows;
}

function errorText(error: unknown) {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "مجوز مدیریت دسته‌بندی، مجموعه یا سایز برای حساب شما فعال نیست.";
  if (error instanceof BrowserApiError && error.status === 400) return "اطلاعات معتبر نیست؛ شناسه انگلیسی باید یکتا باشد.";
  return "ذخیره اطلاعات انجام نشد.";
}

export default function CatalogTaxonomyManager() {
  const [categories, setCategories] = useState<Row[]>([]);
  const [collections, setCollections] = useState<Row[]>([]);
  const [sizes, setSizes] = useState<Size[]>([]);
  const [drafts, setDrafts] = useState<Record<string, { name: string; slug: string; position: string }>>({});
  const [sizeDraft, setSizeDraft] = useState({ code: "", label: "", position: "0" });
  const [editingSize, setEditingSize] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    const [categoryRows, collectionRows, sizeRows] = await Promise.all([
      all<Row>("/api/admin/catalog/categories/"),
      all<Row>("/api/admin/catalog/collections/"),
      all<Size>("/api/admin/catalog/sizes/"),
    ]);
    setCategories(categoryRows);
    setCollections(collectionRows);
    setSizes(sizeRows);
  }, []);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(refresh).catch((e: unknown) => { if (active) setError(errorText(e)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refresh]);

  async function saveRow(kind: "categories" | "collections", row?: Row) {
    const key = kind + ":" + (row?.id ?? "new");
    const draft = drafts[key] ?? { name: "", slug: "", position: String((kind === "categories" ? categories : collections).length) };
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest(row ? "PATCH" : "POST",
        row ? `/api/admin/catalog/${kind}/${row.id}/` : `/api/admin/catalog/${kind}/`,
        { name: draft.name.trim(), slug: draft.slug.trim(), position: Number(draft.position), ...(row ? {} : { is_active: true }) });
      setDrafts((old) => { const next = { ...old }; delete next[key]; return next; });
      await refresh();
      setNotice(kind === "categories" ? "دسته‌بندی ذخیره شد." : "مجموعه ذخیره شد.");
    } catch (e) { setError(errorText(e)); }
    finally { setSaving(false); }
  }

  async function toggleRow(kind: "categories" | "collections", row: Row) {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest("PATCH", `/api/admin/catalog/${kind}/${row.id}/`, { is_active: !row.is_active });
      await refresh();
      setNotice(row.is_active ? "رکورد غیرفعال شد؛ سابقه و ارتباط محصولات حفظ شد." : "رکورد دوباره فعال شد.");
    } catch (e) { setError(errorText(e)); }
    finally { setSaving(false); }
  }

  async function saveSize(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true); setError(""); setNotice("");
    try {
      const payload = { code: sizeDraft.code.trim(), label: sizeDraft.label.trim(), position: Number(sizeDraft.position) };
      await apiRequest(editingSize ? "PATCH" : "POST", editingSize ? `/api/admin/catalog/sizes/${editingSize}/` : "/api/admin/catalog/sizes/", payload);
      setSizeDraft({ code: "", label: "", position: "0" });
      setEditingSize(null);
      await refresh();
      setNotice("گزینه سایز ذخیره شد.");
    } catch (e) { setError(errorText(e)); }
    finally { setSaving(false); }
  }

  const renderRows = (kind: "categories" | "collections", rows: Row[], heading: string) => (
    <section className="rounded-xl border border-border p-4">
      <h3 className="font-semibold">{heading}</h3>
      <form className="mt-3 grid gap-2 sm:grid-cols-4" onSubmit={(event) => { event.preventDefault(); void saveRow(kind); }}>
        <input className={input} placeholder="نام فارسی" aria-label={heading + " جدید"} value={drafts[kind + ":new"]?.name ?? ""} onChange={(e) => setDrafts((old) => ({ ...old, [kind + ":new"]: { name: e.target.value, slug: old[kind + ":new"]?.slug ?? "", position: old[kind + ":new"]?.position ?? String(rows.length) } }))} required />
        <input className={input} placeholder="شناسه انگلیسی" aria-label="شناسه انگلیسی" dir="ltr" value={drafts[kind + ":new"]?.slug ?? ""} onChange={(e) => setDrafts((old) => ({ ...old, [kind + ":new"]: { name: old[kind + ":new"]?.name ?? "", slug: e.target.value, position: old[kind + ":new"]?.position ?? String(rows.length) } }))} required />
        <input className={input} type="number" min="0" placeholder="ترتیب" aria-label="ترتیب نمایش" value={drafts[kind + ":new"]?.position ?? String(rows.length)} onChange={(e) => setDrafts((old) => ({ ...old, [kind + ":new"]: { name: old[kind + ":new"]?.name ?? "", slug: old[kind + ":new"]?.slug ?? "", position: e.target.value } }))} />
        <button className={primary} disabled={saving}>افزودن</button>
      </form>
      <div className="mt-4 space-y-2">
        {rows.map((row) => {
          const key = kind + ":" + row.id;
          const draft = drafts[key] ?? { name: row.name, slug: row.slug, position: String(row.position) };
          return <div key={row.id} className="grid gap-2 rounded-lg bg-muted/40 p-3 sm:grid-cols-[1fr_1fr_90px_auto_auto]">
            <input className={input} aria-label={"نام " + row.name} value={draft.name} onChange={(e) => setDrafts((old) => ({ ...old, [key]: { ...draft, name: e.target.value } }))} />
            <input className={input} aria-label={"شناسه " + row.name} dir="ltr" value={draft.slug} onChange={(e) => setDrafts((old) => ({ ...old, [key]: { ...draft, slug: e.target.value } }))} />
            <input className={input} aria-label={"ترتیب " + row.name} type="number" min="0" value={draft.position} onChange={(e) => setDrafts((old) => ({ ...old, [key]: { ...draft, position: e.target.value } }))} />
            <button type="button" className={secondary} disabled={saving} onClick={() => void saveRow(kind, row)}>ذخیره</button>
            <button type="button" className={secondary} disabled={saving} onClick={() => void toggleRow(kind, row)}>{row.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}</button>
          </div>;
        })}
      </div>
    </section>
  );

  return <section className="mb-7 rounded-2xl border border-border bg-card p-5">
    <div className="mb-4"><h2 className="text-lg font-bold">مدیریت ساختار کاتالوگ</h2><p className="mt-1 text-xs text-muted-foreground">دسته‌بندی و مجموعه قابل غیرفعال‌سازی‌اند؛ گزینه‌های سایز به‌دلیل ارتباط با تنوع‌ها حذف نمی‌شوند.</p></div>
    {error && <p role="alert" className="mb-3 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
    {notice && <p role="status" className="mb-3 rounded-lg bg-muted p-3 text-sm">{notice}</p>}
    {loading ? <p className="py-4 text-sm text-muted-foreground">در حال دریافت اطلاعات…</p> : <div className="grid gap-4 xl:grid-cols-2">
      {renderRows("categories", categories, "دسته‌بندی‌ها")}
      {renderRows("collections", collections, "مجموعه‌ها")}
      <section className="rounded-xl border border-border p-4 xl:col-span-2">
        <h3 className="font-semibold">گزینه‌های سایز</h3>
        <form onSubmit={saveSize} className="mt-3 grid gap-2 sm:grid-cols-4">
          <input className={input} placeholder="کد انگلیسی (مثلاً M)" dir="ltr" value={sizeDraft.code} onChange={(e) => setSizeDraft((old) => ({ ...old, code: e.target.value }))} required />
          <input className={input} placeholder="عنوان نمایشی (مثلاً متوسط)" value={sizeDraft.label} onChange={(e) => setSizeDraft((old) => ({ ...old, label: e.target.value }))} required />
          <input className={input} type="number" min="0" placeholder="ترتیب" value={sizeDraft.position} onChange={(e) => setSizeDraft((old) => ({ ...old, position: e.target.value }))} />
          <button className={primary} disabled={saving}>{editingSize ? "ذخیره تغییرات" : "افزودن سایز"}</button>
        </form>
        <div className="mt-4 flex flex-wrap gap-2">{sizes.map((size) => <button key={size.id} type="button" className={secondary} onClick={() => { setEditingSize(size.id); setSizeDraft({ code: size.code, label: size.label, position: String(size.position) }); }}>{size.label} ({size.code})</button>)}</div>
        {editingSize && <button type="button" className="mt-3 text-xs text-muted-foreground underline" onClick={() => { setEditingSize(null); setSizeDraft({ code: "", label: "", position: "0" }); }}>لغو ویرایش سایز</button>}
      </section>
    </div>}
  </section>;
}
