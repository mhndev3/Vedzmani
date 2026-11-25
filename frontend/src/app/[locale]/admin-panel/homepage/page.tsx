"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type SectionType = "categories" | "products" | "newest_products";
type SectionStatus = "draft" | "published";
type Entry = { id: number; name: string; slug?: string; is_active: boolean; category?: number };
type Section = {
  id: number; title: string; section_label: string; eyebrow: string; section_type: SectionType; status: SectionStatus;
  position: number; item_limit: number; show_view_all: boolean; view_all_url: string;
  categories: number[]; products: number[];
};
type Revision = { id: number; action: "baseline" | "created" | "updated" | "rollback"; snapshot: Partial<Section>; created_by_label: string; created_at: string };
type Page<T> = { results: T[]; next: string | null };
const inputClass = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary";
const primaryClass = "rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondaryClass = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";

async function getAll<T>(path: string): Promise<T[]> {
  const rows: T[] = [];
  let next: string | null = path;
  let pages = 0;
  while (next && pages < 40) {
    const page: Page<T> = await apiRequest<Page<T>>("GET", next);
    rows.push(...page.results);
    if (!page.next) break;
    const url = new URL(page.next, window.location.origin);
    next = url.pathname + url.search;
    pages += 1;
  }
  return rows;
}
function errorText(error: unknown): string {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "مجوز مشاهده یا ویرایش بخش‌های صفحه اصلی را ندارید.";
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "ذخیره اطلاعات انجام نشد. ورودی‌ها و انتخاب‌ها را بررسی کنید.";
}
const blank = (): Omit<Section, "id"> => ({
  title: "", section_label: "", eyebrow: "", section_type: "newest_products", status: "draft",
  position: 0, item_limit: 8, show_view_all: true, view_all_url: "/products",
  categories: [], products: [],
});

export default function AdminHomepagePage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [sections, setSections] = useState<Section[]>([]);
  const [categories, setCategories] = useState<Entry[]>([]);
  const [products, setProducts] = useState<Entry[]>([]);
  const [draft, setDraft] = useState<Omit<Section, "id">>(blank());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState(false);
  const [historyFor, setHistoryFor] = useState<number | null>(null);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [s, c, p] = await Promise.all([
        apiRequest<Section[]>("GET", "/api/admin/homepage/sections/"),
        getAll<Entry>("/api/admin/catalog/categories/"),
        getAll<Entry>("/api/admin/catalog/products/"),
      ]);
      setSections(s.sort((a,b) => a.position - b.position || a.id - b.id));
      setCategories(c.filter(x => x.is_active));
      setProducts(p.filter(x => x.is_active));
    } catch (e) { setError(errorText(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { let live = true; void (async () => {
    try {
      const [s,c,p] = await Promise.all([
        apiRequest<Section[]>("GET", "/api/admin/homepage/sections/"),
        getAll<Entry>("/api/admin/catalog/categories/"),
        getAll<Entry>("/api/admin/catalog/products/"),
      ]);
      if (!live) return;
      const ordered = [...s].sort((a,b) => a.position - b.position || a.id - b.id);
      setSections(ordered);
      setCategories(c.filter(x => x.is_active)); setProducts(p.filter(x => x.is_active));

      const query = new URLSearchParams(window.location.search);
      const editId = Number(query.get("edit"));
      const target = Number.isSafeInteger(editId) && editId > 0 ? ordered.find(item => item.id === editId) : undefined;
      if (target) {
        const { id, ...values } = target;
        setEditingId(id);
        setDraft(values);
        setNotice("بخش انتخاب‌شده برای ویرایش باز شد.");
      } else if (query.get("new") === "1") {
        const requestedPosition = Number(query.get("position"));
        const position = Number.isSafeInteger(requestedPosition) && requestedPosition >= 0
          ? Math.min(requestedPosition, ordered.length)
          : ordered.length;
        setEditingId(null);
        setDraft({ ...blank(), position });
        setNotice("فرم ساخت بخش جدید در جایگاه انتخاب‌شده باز شد.");
      }
    } catch(e) { if (live) setError(errorText(e)); }
    finally { if (live) setLoading(false); }
  })(); return () => { live = false; }; }, []);

  const visibleProducts = useMemo(() => {
    const q = search.trim().toLocaleLowerCase();
    return products.filter(p => !q || p.name.toLocaleLowerCase().includes(q) || String(p.id) === q).slice(0, 250);
  }, [products, search]);

  function update<K extends keyof Omit<Section, "id">>(key: K, value: Omit<Section, "id">[K]) {
    setDraft(old => ({ ...old, [key]: value }));
  }
  function newSection() { setEditingId(null); setDraft({ ...blank(), position: sections.length }); setPreview(false); setNotice(""); setError(""); }
  function editSection(section: Section) {
    const { id: _id, ...values } = section;
    setEditingId(section.id); setDraft(values); setPreview(false); setNotice(""); setError("");
  }
  function changeType(type: SectionType) {
    setDraft(old => ({ ...old, section_type: type, categories: [], products: [] }));
  }
  function toggleId(key: "categories" | "products", id: number) {
    setDraft(old => ({ ...old, [key]: old[key].includes(id) ? old[key].filter(x => x !== id) : [...old[key], id] }));
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    if (draft.show_view_all && draft.view_all_url && (!draft.view_all_url.startsWith("/") || draft.view_all_url.startsWith("//"))) {
      setError("لینک مشاهده همه باید یک مسیر داخلی سایت باشد؛ نشانی خارجی مجاز نیست."); setSaving(false); return;
    }
    const payload = {
      ...draft,
      title: draft.title.trim(),
      eyebrow: draft.eyebrow.trim(),
      view_all_url: draft.show_view_all ? draft.view_all_url.trim() : "",
    };
    try {
      if (editingId === null) {
        const ordered = [...sections].sort((a, b) => a.position - b.position || a.id - b.id);
        const insertionPosition = Math.max(0, Math.min(ordered.length, payload.position));
        for (let index = ordered.length - 1; index >= insertionPosition; index -= 1) {
          await apiRequest<Section>("PATCH", `/api/admin/homepage/sections/${ordered[index].id}/`, {
            position: index + 1,
          });
        }
        await apiRequest<Section>("POST", "/api/admin/homepage/sections/", {
          ...payload,
          position: insertionPosition,
        });
      } else {
        await apiRequest<Section>("PATCH", `/api/admin/homepage/sections/${editingId}/`, payload);
      }
      newSection();
      setNotice("تغییرات ذخیره شد. برای نمایش در فروشگاه، وضعیت انتشار را فعال کنید.");
      await refresh();
    } catch(e) { setError(errorText(e)); }
    finally { setSaving(false); }
  }
  async function openHistory(section: Section) {
    if (historyFor === section.id) { setHistoryFor(null); setRevisions([]); return; }
    setHistoryFor(section.id); setHistoryLoading(true); setRevisions([]); setError("");
    try {
      const rows = await apiRequest<Revision[]>("GET", `/api/admin/homepage/sections/${section.id}/revisions/`);
      setRevisions(rows);
    } catch (e) { setError(errorText(e)); setRevisions([]); }
    finally { setHistoryLoading(false); }
  }

  async function rollback(section: Section, revision: Revision) {
    if (!window.confirm("این نسخه جایگزین تنظیمات فعلی این بخش شود؟ نسخه فعلی نیز در تاریخچه باقی می‌ماند.")) return;
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<Section>("POST", `/api/admin/homepage/sections/${section.id}/revisions/`, { revision_id: revision.id });
      setNotice("نسخه انتخاب‌شده بازگردانی شد؛ رویداد بازگردانی نیز در تاریخچه ثبت شد.");
      await refresh();
      const rows = await apiRequest<Revision[]>("GET", `/api/admin/homepage/sections/${section.id}/revisions/`);
      setRevisions(rows);
    } catch (e) { setError(errorText(e)); }
    finally { setSaving(false); }
  }

  async function removeSection(section: Section) {
    if (!window.confirm(`بخش «${section.title}» حذف شود؟ نسخه‌های ذخیره‌شده این بخش نیز حذف خواهند شد.`)) return;
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<void>("DELETE", `/api/admin/homepage/sections/${section.id}/`);
      if (historyFor === section.id) { setHistoryFor(null); setRevisions([]); }
      if (editingId === section.id) newSection();
      await refresh();
      setNotice("بخش صفحه اصلی حذف شد.");
    } catch (e) { setError(errorText(e)); }
    finally { setSaving(false); }
  }

  async function publish(section: Section) {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<Section>("PATCH", `/api/admin/homepage/sections/${section.id}/`, { status: section.status === "published" ? "draft" : "published" });
      setNotice(section.status === "published" ? "بخش به پیش‌نویس برگشت." : "بخش منتشر شد و در صفحه اصلی نمایش داده می‌شود.");
      await refresh();
    } catch(e) { setError(errorText(e)); }
    finally { setSaving(false); }
  }
  async function move(section: Section, delta: number) {
    const index = sections.findIndex(x => x.id === section.id); const other = sections[index + delta];
    if (!other) return;
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<Section>("PATCH", `/api/admin/homepage/sections/${section.id}/`, { position: other.position });
      await apiRequest<Section>("PATCH", `/api/admin/homepage/sections/${other.id}/`, { position: section.position });
      await refresh(); setNotice("ترتیب بخش‌ها تغییر کرد.");
    } catch(e) { setError(errorText(e)); await refresh(); }
    finally { setSaving(false); }
  }

  return <main dir="rtl" className="mx-auto w-full max-w-7xl px-4 py-8 sm:py-10">
    <div className="mb-7">
      <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
      <h1 className="mt-3 text-2xl font-bold sm:text-3xl">مدیریت صفحه اصلی</h1>
      <p className="mt-2 text-sm leading-7 text-muted-foreground">بخش‌های تازه به صفحه فعلی اضافه می‌شوند و زیر دسته‌بندی‌ها و «جدیدترین‌ها» قرار می‌گیرند؛ ساخت بخش جدید، بخش‌های قبلی را حذف یا جایگزین نمی‌کند.</p>
    </div>
    {notice && <p role="status" className="mb-4 rounded-xl border border-border bg-muted p-3 text-sm">{notice}</p>}
    {error && <p role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</p>}
    <div className="grid gap-6 xl:grid-cols-[minmax(320px,0.9fr)_minmax(0,1.1fr)]">
      <section className="rounded-2xl border border-border bg-card p-5">
        <div className="flex items-center justify-between gap-3"><h2 className="font-bold">{editingId === null ? "ساخت بخش جدید" : "ویرایش بخش"}</h2><button type="button" className={secondaryClass} onClick={newSection}>بخش جدید</button></div>
        <form onSubmit={save} className="mt-4 space-y-4">
          <label className="block text-sm">عنوان بخش<input required maxLength={120} value={draft.title} onChange={e => update("title", e.target.value)} className={inputClass} /></label>
          <label className="block text-sm">نوع یا برچسب دلخواه بخش (متن آزاد)<input maxLength={80} value={draft.section_label} onChange={e => update("section_label", e.target.value)} className={inputClass} placeholder="مثلاً پیشنهاد ویژه، اکسسوری، تخفیف‌ها" /></label>
          <label className="block text-sm">متن کوچک بالای عنوان (اختیاری)<input maxLength={120} value={draft.eyebrow} onChange={e => update("eyebrow", e.target.value)} className={inputClass} /></label>
          <label className="block text-sm">چیدمان محتوا<select value={draft.section_type} onChange={e => changeType(e.target.value as SectionType)} className={inputClass}>
            <option value="categories">شبکه دسته‌بندی‌ها</option><option value="products">محصولات انتخابی</option><option value="newest_products">جدیدترین محصولات</option>
          </select><span className="mt-1 block text-xs text-muted-foreground">نام بخش آزاد است؛ چیدمان محتوا از قالب‌های پشتیبانی‌شده انتخاب می‌شود تا صفحه فروشگاه خراب نشود.</span></label>
          {draft.section_type === "categories" && <fieldset className="rounded-xl border border-border p-3"><legend className="px-1 text-sm font-medium">انتخاب دسته‌بندی‌ها</legend><div className="max-h-48 space-y-2 overflow-y-auto">{categories.map(c => <label key={c.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.categories.includes(c.id)} onChange={() => toggleId("categories", c.id)} />{c.name}</label>)}</div></fieldset>}
          {(draft.section_type === "products" || draft.section_type === "newest_products") && (
            <fieldset className="rounded-xl border border-border p-3">
              <legend className="px-1 text-sm font-medium">
                {draft.section_type === "newest_products" ? "محصولات منتخب در ابتدای بخش (اختیاری)" : "انتخاب کارت‌های محصول"}
              </legend>
              {draft.section_type === "newest_products" && (
                <p className="mb-3 text-xs leading-6 text-muted-foreground">کارت‌های انتخاب‌شده ابتدا نمایش داده می‌شوند و جای خالی با جدیدترین محصولات فعال پر می‌شود.</p>
              )}
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="جستجوی محصول…" className={inputClass + " mb-3"} />
              <div className="max-h-56 space-y-2 overflow-y-auto">
                {visibleProducts.map(p => (
                  <label key={p.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={draft.products.includes(p.id)} onChange={() => toggleId("products", p.id)} />
                    {p.name}<span className="text-xs text-muted-foreground">#{p.id}</span>
                  </label>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">حداکثر ۲۵۰ نتیجه نخست برای جستجو بارگذاری شده است.</p>
            </fieldset>
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block text-sm">تعداد نمایش<input type="number" min="1" max="24" value={draft.item_limit} onChange={e => update("item_limit", Math.max(1, Math.min(24, Number(e.target.value))))} className={inputClass} /></label>
            <label className="block text-sm">جایگاه نمایش<input type="number" min="1" value={draft.position + 1} onChange={e => update("position", Math.max(0, Number(e.target.value) - 1))} className={inputClass} /></label>
            <label className="block text-sm">وضعیت<select value={draft.status} onChange={e => update("status", e.target.value as SectionStatus)} className={inputClass}><option value="draft">پیش‌نویس</option><option value="published">منتشرشده</option></select></label>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.show_view_all} onChange={e => update("show_view_all", e.target.checked)} />نمایش لینک «مشاهده همه»</label>
          {draft.show_view_all && <label className="block text-sm">مسیر داخلی لینک<input value={draft.view_all_url} onChange={e => update("view_all_url", e.target.value)} dir="ltr" placeholder="/products" className={inputClass} /><span className="mt-1 block text-xs text-muted-foreground">فقط مسیر داخلی مانند /products یا /categories/knitwear</span></label>}
          <div className="flex flex-wrap gap-2"><button type="submit" disabled={saving || !draft.title.trim()} className={primaryClass}>{saving ? "در حال ذخیره…" : editingId === null ? "ساخت بخش" : "ذخیره تغییرات"}</button><button type="button" disabled={saving} className={secondaryClass} onClick={() => setPreview(v => !v)}>{preview ? "بستن پیش‌نمایش" : "پیش‌نمایش تنظیمات"}</button></div>
        </form>
        {preview && <div className="mt-5 rounded-xl border border-dashed border-primary/40 p-4"><p className="text-xs text-muted-foreground">پیش‌نمایش تنظیمات، بدون انتشار در فروشگاه</p>{(draft.section_label || draft.eyebrow) && <p className="mt-3 text-xs text-muted-foreground">{draft.section_label || draft.eyebrow}</p>}<h3 className="mt-1 text-lg font-bold">{draft.title || "عنوان بخش"}</h3><p className="mt-2 text-sm text-muted-foreground">{draft.section_type === "categories" ? `${draft.categories.length} دسته‌بندی انتخاب شده` : draft.section_type === "products" ? `${draft.products.length} محصول انتخاب شده` : "جدیدترین محصولات فعال"} · نمایش {draft.item_limit} مورد</p></div>}
      </section>
      <section className="rounded-2xl border border-border bg-card p-5">
        <div className="mb-4 flex items-center justify-between gap-3"><h2 className="font-bold">بخش‌های تعریف‌شده</h2><span className="text-xs text-muted-foreground">{sections.length.toLocaleString("fa-IR")} بخش</span></div>
        {loading ? <p className="py-10 text-center text-sm text-muted-foreground">در حال دریافت اطلاعات…</p> : sections.length === 0 ? <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">هنوز بخشی ساخته نشده است.</p> : <div className="space-y-3">{sections.map((s,index) => <article key={s.id} className="rounded-xl border border-border p-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{s.title}</h3><span className={s.status === "published" ? "rounded-full bg-primary/10 px-2 py-1 text-xs" : "rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground"}>{s.status === "published" ? "منتشرشده" : "پیش‌نویس"}</span></div><p className="mt-2 text-xs text-muted-foreground">{s.section_label || (s.section_type === "categories" ? "دسته‌بندی‌ها" : s.section_type === "products" ? "محصولات منتخب" : "جدیدترین محصولات")} · {s.item_limit} مورد · ترتیب {s.position + 1} پس از بخش‌های اصلی</p></div>
            <div className="flex flex-wrap gap-2"><button type="button" disabled={saving || index===0} onClick={() => void move(s,-1)} className={secondaryClass}>↑</button><button type="button" disabled={saving || index===sections.length-1} onClick={() => void move(s,1)} className={secondaryClass}>↓</button><button type="button" disabled={saving} onClick={() => editSection(s)} className={secondaryClass}>ویرایش</button><button type="button" disabled={saving} onClick={() => void openHistory(s)} className={secondaryClass}>{historyFor === s.id ? "بستن تاریخچه" : "تاریخچه نسخه‌ها"}</button><button type="button" disabled={saving} onClick={() => void publish(s)} className={primaryClass}>{s.status === "published" ? "تبدیل به پیش‌نویس" : "انتشار"}</button><button type="button" disabled={saving} onClick={() => void removeSection(s)} className={secondaryClass}>حذف بخش</button></div>
          </div>
          {historyFor === s.id && <div className="mt-4 border-t border-border pt-4">
            <h4 className="text-sm font-semibold">تاریخچه نسخه‌های «{s.title}»</h4>
            {historyLoading ? <p className="mt-3 text-xs text-muted-foreground">در حال دریافت تاریخچه…</p> : revisions.length === 0 ? <p className="mt-3 text-xs text-muted-foreground">نسخه‌ای ثبت نشده است.</p> : <div className="mt-3 space-y-2">
              {revisions.map((revision, revisionIndex) => <div key={revision.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted/50 p-3">
                <div>
                  <p className="text-sm font-medium">{revision.action === "baseline" ? "نسخه پایه پیش از فعال‌شدن تاریخچه" : revision.action === "created" ? "ایجاد اولیه" : revision.action === "rollback" ? "بازگردانی نسخه" : "ویرایش"}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{revision.snapshot.title || "بدون عنوان"} · {new Date(revision.created_at).toLocaleString("fa-IR")} · {revision.created_by_label}</p>
                </div>
                {revisionIndex > 0 && <button type="button" disabled={saving} onClick={() => void rollback(s, revision)} className={secondaryClass}>بازگردانی این نسخه</button>}
              </div>)}
            </div>}
          </div>}
        </article>)}</div>}
        <p className="mt-5 text-xs leading-6 text-muted-foreground">برای پنهان‌کردن موقت، وضعیت را به پیش‌نویس تغییر دهید. حذف بخش، نسخه‌های تاریخچه همان بخش را نیز پاک می‌کند. بخش‌های منتشرشده به ترتیب بالا در صفحه اصلی نمایش داده می‌شوند.</p>
      </section>
    </div>
  </main>;
}
