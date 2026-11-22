"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import Image from "next/image";
import { useParams } from "next/navigation";
import { apiMultipartRequest, apiRequest, BrowserApiError } from "@/lib/browser-api";

type Banner = {
  id: number; title: string; subtitle: string; alt_text: string;
  desktop_image_url: string; mobile_image_url: string | null;
  cta_label: string; cta_url: string; position: number; status: "draft" | "published";
  starts_at: string | null; ends_at: string | null;
};
type Revision = { id: number; action: "baseline" | "created" | "updated" | "rollback"; snapshot: Partial<Banner>; created_by_label: string; created_at: string };
type MediaItem = { id: string; source: "product" | "banner"; source_label: string; title: string; alt_text: string; url: string; thumbnail_url: string; width: number | null; height: number | null; owner_label: string };
type MediaPage = { count: number; next: string | null; previous: string | null; results: MediaItem[] };
type Draft = {
  title: string; subtitle: string; alt_text: string; cta_label: string; cta_url: string;
  position: number; status: "draft" | "published"; starts_at: string; ends_at: string;
};
const blank = (): Draft => ({
  title: "", subtitle: "", alt_text: "", cta_label: "", cta_url: "",
  position: 0, status: "draft", starts_at: "", ends_at: "",
});
const field = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary";
const primary = "rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondary = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";

function localDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
}
function isoDate(value: string) {
  return value ? new Date(value).toISOString() : "";
}
function message(error: unknown) {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "مجوز مدیریت بنرها را ندارید.";
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "ذخیره انجام نشد. فایل‌ها و اطلاعات واردشده را بررسی کنید.";
}

export default function AdminHomepageBannersPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [banners, setBanners] = useState<Banner[]>([]);
  const [draft, setDraft] = useState<Draft>(blank());
  const [desktopFile, setDesktopFile] = useState<File | null>(null);
  const [mobileFile, setMobileFile] = useState<File | null>(null);
  const [desktopMediaRef, setDesktopMediaRef] = useState("");
  const [mobileMediaRef, setMobileMediaRef] = useState("");
  const [pickerTarget, setPickerTarget] = useState<"desktop" | "mobile" | null>(null);
  const [pickerItems, setPickerItems] = useState<MediaItem[]>([]);
  const [pickerQuery, setPickerQuery] = useState("");
  const [pickerAppliedQuery, setPickerAppliedQuery] = useState("");
  const [pickerPage, setPickerPage] = useState(1);
  const [pickerCount, setPickerCount] = useState(0);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [historyFor, setHistoryFor] = useState<number | null>(null);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await apiRequest<Banner[]>("GET", "/api/admin/homepage/banners/");
      setBanners(rows.sort((a, b) => a.position - b.position || a.id - b.id));
      setError("");
    } catch (e) { setError(message(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const rows = await apiRequest<Banner[]>("GET", "/api/admin/homepage/banners/");
        if (active) setBanners(rows.sort((a, b) => a.position - b.position || a.id - b.id));
      } catch (e) {
        if (active) setError(message(e));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, []);

  function reset() {
    setEditingId(null); setDraft({ ...blank(), position: banners.length });
    setDesktopFile(null); setMobileFile(null); setDesktopMediaRef(""); setMobileMediaRef(""); setNotice(""); setError("");
  }
  function edit(banner: Banner) {
    setEditingId(banner.id);
    setDraft({
      title: banner.title, subtitle: banner.subtitle, alt_text: banner.alt_text,
      cta_label: banner.cta_label, cta_url: banner.cta_url, position: banner.position,
      status: banner.status, starts_at: localDate(banner.starts_at), ends_at: localDate(banner.ends_at),
    });
    setDesktopFile(null); setMobileFile(null); setDesktopMediaRef(""); setMobileMediaRef(""); setNotice(""); setError("");
  }
  function set<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft(old => ({ ...old, [key]: value }));
  }

  function openMediaPicker(target: "desktop" | "mobile") {
    setPickerTarget(target);
    setPickerQuery("");
    setPickerAppliedQuery("");
    setPickerPage(1);
    setPickerItems([]);
    setPickerError("");
    setPickerLoading(true);
  }

  useEffect(() => {
    if (!pickerTarget) return;
    let active = true;
    const params = new URLSearchParams({ page: String(pickerPage), source: "all" });
    if (pickerAppliedQuery) params.set("q", pickerAppliedQuery);
    void apiRequest<MediaPage>("GET", `/api/admin/media/?${params.toString()}`)
      .then(result => {
        if (!active) return;
        setPickerItems(result.results);
        setPickerCount(result.count);
        setPickerError("");
      })
      .catch(() => {
        if (!active) return;
        setPickerItems([]);
        setPickerCount(0);
        setPickerError("دریافت تصاویر کتابخانه انجام نشد یا مجوز مشاهده آن‌ها را ندارید.");
      })
      .finally(() => { if (active) setPickerLoading(false); });
    return () => { active = false; };
  }, [pickerTarget, pickerPage, pickerAppliedQuery]);

  function chooseLibraryImage(item: MediaItem) {
    if (pickerTarget === "desktop") {
      setDesktopMediaRef(item.id);
      setDesktopFile(null);
    } else if (pickerTarget === "mobile") {
      setMobileMediaRef(item.id);
      setMobileFile(null);
    }
    setPickerTarget(null);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    if (draft.cta_url && (!draft.cta_url.startsWith("/") || draft.cta_url.startsWith("//") || draft.cta_url.includes("\\"))) {
      setError("لینک دکمه باید مسیر داخلی سایت باشد."); setSaving(false); return;
    }
    if (draft.status === "published" && editingId === null && !desktopFile && !desktopMediaRef) {
      setError("برای انتشار بنر، تصویر دسکتاپ الزامی است."); setSaving(false); return;
    }
    const data = new FormData();
    for (const [key, value] of Object.entries(draft)) {
      if (key === "starts_at" || key === "ends_at") data.set(key, isoDate(String(value)));
      else data.set(key, String(value));
    }
    if (desktopFile) data.set("desktop_image", desktopFile);
    else if (desktopMediaRef) data.set("desktop_image_media_ref", desktopMediaRef);
    if (mobileFile) data.set("mobile_image", mobileFile);
    else if (mobileMediaRef) data.set("mobile_image_media_ref", mobileMediaRef);
    if (editingId === null && !desktopFile && !desktopMediaRef) {
      setError("تصویر دسکتاپ را انتخاب کنید."); setSaving(false); return;
    }
    try {
      await apiMultipartRequest(editingId === null ? "POST" : "PATCH",
        editingId === null ? "/api/admin/homepage/banners/" : `/api/admin/homepage/banners/${editingId}/`, data);
      reset(); setNotice("بنر ذخیره شد.");
      await refresh();
    } catch (e) { setError(message(e)); }
    finally { setSaving(false); }
  }

  async function openHistory(banner: Banner) {
    if (historyFor === banner.id) { setHistoryFor(null); setRevisions([]); return; }
    setHistoryFor(banner.id); setHistoryLoading(true); setRevisions([]); setError("");
    try {
      const rows = await apiRequest<Revision[]>("GET", `/api/admin/homepage/banners/${banner.id}/revisions/`);
      setRevisions(rows);
    } catch (e) { setError(message(e)); }
    finally { setHistoryLoading(false); }
  }

  async function rollback(banner: Banner, revision: Revision) {
    if (!window.confirm("محتوا، وضعیت انتشار و تصاویر این نسخه جایگزین وضعیت فعلی بنر شود؟")) return;
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest("POST", `/api/admin/homepage/banners/${banner.id}/revisions/`, { revision_id: revision.id });
      setNotice("نسخه انتخاب‌شده بازگردانی و در تاریخچه ثبت شد.");
      await refresh();
      const rows = await apiRequest<Revision[]>("GET", `/api/admin/homepage/banners/${banner.id}/revisions/`);
      setRevisions(rows);
    } catch (e) { setError(message(e)); }
    finally { setSaving(false); }
  }

  async function togglePublish(banner: Banner) {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest("PATCH", `/api/admin/homepage/banners/${banner.id}/`, {
        status: banner.status === "published" ? "draft" : "published",
      });
      setNotice(banner.status === "published" ? "بنر به پیش‌نویس برگشت." : "بنر منتشر شد.");
      await refresh();
    } catch (e) { setError(message(e)); }
    finally { setSaving(false); }
  }

  async function move(banner: Banner, delta: number) {
    const index = banners.findIndex(item => item.id === banner.id);
    const other = banners[index + delta];
    if (!other) return;
    setSaving(true); setError("");
    try {
      await apiRequest("PATCH", `/api/admin/homepage/banners/${banner.id}/`, { position: other.position });
      await apiRequest("PATCH", `/api/admin/homepage/banners/${other.id}/`, { position: banner.position });
      await refresh(); setNotice("ترتیب بنرها تغییر کرد.");
    } catch (e) { setError(message(e)); await refresh(); }
    finally { setSaving(false); }
  }

  const current = banners.find(item => item.id === editingId);
  return <main dir="rtl" className="mx-auto w-full max-w-7xl px-4 py-8 sm:py-10">
    <div className="mb-7">
      <Link href={`/${locale}/admin-panel/homepage`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به مدیریت صفحه اصلی</Link>
      <h1 className="mt-3 text-2xl font-bold sm:text-3xl">مدیریت بنرهای صفحه اصلی</h1>
      <p className="mt-2 text-sm leading-7 text-muted-foreground">تصویر دسکتاپ و موبایل، متن جایگزین، دکمه، زمان نمایش و ترتیب بنرها را مدیریت کنید. پیش‌نویس‌ها در فروشگاه دیده نمی‌شوند.</p>
    </div>
    {notice && <p role="status" className="mb-4 rounded-xl border border-border bg-muted p-3 text-sm">{notice}</p>}
    {error && <p role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</p>}
    <div className="grid gap-6 xl:grid-cols-[minmax(320px,0.9fr)_minmax(0,1.1fr)]">
      <section className="rounded-2xl border border-border bg-card p-5">
        <div className="flex items-center justify-between gap-3"><h2 className="font-bold">{editingId === null ? "افزودن بنر" : "ویرایش بنر"}</h2><button type="button" className={secondary} onClick={reset}>بنر جدید</button></div>
        <form onSubmit={save} className="mt-4 space-y-4">
          <label className="block text-sm">عنوان داخلی بنر<input maxLength={120} value={draft.title} onChange={e => set("title", e.target.value)} className={field} /></label>
          <label className="block text-sm">متن توضیحی<input maxLength={240} value={draft.subtitle} onChange={e => set("subtitle", e.target.value)} className={field} /></label>
          <label className="block text-sm">متن جایگزین تصویر<input required maxLength={200} value={draft.alt_text} onChange={e => set("alt_text", e.target.value)} className={field} /></label>
          <div className="space-y-2">
            <label className="block text-sm">تصویر دسکتاپ (JPEG / PNG / WebP، حداکثر ۸ مگابایت)
              <input type="file" accept="image/jpeg,image/png,image/webp" onChange={e => { setDesktopFile(e.target.files?.[0] ?? null); setDesktopMediaRef(""); }} className={field} />
            </label>
            <button type="button" className={secondary} onClick={() => openMediaPicker("desktop")}>انتخاب از کتابخانه رسانه</button>
            {desktopMediaRef && <p className="text-xs text-muted-foreground">تصویر انتخاب‌شده از کتابخانه برای دسکتاپ استفاده می‌شود.</p>}
            {current?.desktop_image_url && !desktopFile && !desktopMediaRef && <p className="text-xs text-muted-foreground">تصویر فعلی دسکتاپ حفظ می‌شود.</p>}
          </div>
          <div className="space-y-2">
            <label className="block text-sm">تصویر موبایل (اختیاری)
              <input type="file" accept="image/jpeg,image/png,image/webp" onChange={e => { setMobileFile(e.target.files?.[0] ?? null); setMobileMediaRef(""); }} className={field} />
            </label>
            <button type="button" className={secondary} onClick={() => openMediaPicker("mobile")}>انتخاب از کتابخانه رسانه</button>
            {mobileMediaRef && <p className="text-xs text-muted-foreground">تصویر انتخاب‌شده از کتابخانه برای موبایل استفاده می‌شود.</p>}
            {current?.mobile_image_url && !mobileFile && !mobileMediaRef && <p className="text-xs text-muted-foreground">تصویر فعلی موبایل حفظ می‌شود.</p>}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">متن دکمه (اختیاری)<input maxLength={60} value={draft.cta_label} onChange={e => set("cta_label", e.target.value)} className={field} /></label>
            <label className="block text-sm">مسیر داخلی دکمه<input dir="ltr" maxLength={240} placeholder="/products" value={draft.cta_url} onChange={e => set("cta_url", e.target.value)} className={field} /></label>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">شروع نمایش<input type="datetime-local" value={draft.starts_at} onChange={e => set("starts_at", e.target.value)} className={field} /></label>
            <label className="block text-sm">پایان نمایش<input type="datetime-local" value={draft.ends_at} onChange={e => set("ends_at", e.target.value)} className={field} /></label>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">ترتیب نمایش<input type="number" min="0" value={draft.position} onChange={e => set("position", Math.max(0, Number(e.target.value)))} className={field} /></label>
            <label className="block text-sm">وضعیت<select value={draft.status} onChange={e => set("status", e.target.value as Draft["status"])} className={field}><option value="draft">پیش‌نویس</option><option value="published">منتشرشده</option></select></label>
          </div>
          <div className="flex flex-wrap gap-2"><button type="submit" disabled={saving} className={primary}>{saving ? "در حال ذخیره…" : editingId === null ? "ذخیره بنر" : "ذخیره تغییرات"}</button></div>
        </form>
      </section>
      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="mb-4 font-bold">بنرهای ثبت‌شده <span className="text-xs font-normal text-muted-foreground">({banners.length.toLocaleString("fa-IR")})</span></h2>
        {loading ? <p className="py-10 text-center text-sm text-muted-foreground">در حال دریافت…</p> : banners.length === 0 ? <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">هنوز بنری ثبت نشده است.</p> : <div className="space-y-4">{banners.map((banner, index) => <article key={banner.id} className="rounded-xl border border-border p-4">
          <div className="relative mb-3 aspect-[2048/746] overflow-hidden rounded-lg bg-muted">
            {/* Admin preview uses the same-origin media URL returned by the API. */}
            <Image src={banner.desktop_image_url} alt={banner.alt_text} fill sizes="(max-width: 768px) 100vw, 720px" unoptimized className="object-cover" />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h3 className="font-semibold">{banner.title || `بنر شماره ${banner.id}`}</h3><p className="mt-1 text-xs text-muted-foreground">{banner.status === "published" ? "منتشرشده" : "پیش‌نویس"} · ترتیب {banner.position + 1}{banner.mobile_image_url ? " · تصویر موبایل دارد" : ""}</p></div>
            <div className="flex flex-wrap gap-2"><button type="button" disabled={saving || index===0} onClick={() => void move(banner,-1)} className={secondary}>↑</button><button type="button" disabled={saving || index===banners.length-1} onClick={() => void move(banner,1)} className={secondary}>↓</button><button type="button" disabled={saving} onClick={() => edit(banner)} className={secondary}>ویرایش</button><button type="button" disabled={saving} onClick={() => void openHistory(banner)} className={secondary}>{historyFor === banner.id ? "بستن تاریخچه" : "تاریخچه نسخه‌ها"}</button><button type="button" disabled={saving} onClick={() => void togglePublish(banner)} className={primary}>{banner.status === "published" ? "پیش‌نویس" : "انتشار"}</button></div>
          </div>
        {historyFor === banner.id && <div className="mt-4 border-t border-border pt-4">
             <h4 className="text-sm font-semibold">تاریخچه نسخه‌ها</h4>
             {historyLoading ? <p className="mt-3 text-xs text-muted-foreground">در حال دریافت تاریخچه…</p> : revisions.length === 0 ? <p className="mt-3 text-xs text-muted-foreground">نسخه‌ای ثبت نشده است.</p> : <div className="mt-3 space-y-2">
               {revisions.map((revision, revisionIndex) => <div key={revision.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted/50 p-3">
                 <div><p className="text-sm font-medium">{revision.action === "baseline" ? "نسخه پایه" : revision.action === "created" ? "ایجاد اولیه" : revision.action === "rollback" ? "بازگردانی" : "ویرایش"}</p>
                   <p className="mt-1 text-xs text-muted-foreground">{revision.snapshot.title || "بدون عنوان"} · {new Date(revision.created_at).toLocaleString("fa-IR")} · {revision.created_by_label}</p></div>
                 {revisionIndex > 0 && <button type="button" disabled={saving} onClick={() => void rollback(banner, revision)} className={secondary}>بازگردانی این نسخه</button>}
               </div>)}
             </div>}
           </div>}
         </article>)}</div>}
        <p className="mt-5 text-xs leading-6 text-muted-foreground">حذف فیزیکی بنرها در این مرحله وجود ندارد. برای توقف نمایش، وضعیت را به پیش‌نویس تغییر دهید. زمان‌بندی بر اساس ساعت سرور فروشگاه اعمال می‌شود.</p>
      </section>
    </div>
    {pickerTarget && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3 sm:p-6" role="dialog" aria-modal="true" aria-label="انتخاب تصویر از کتابخانه">
      <section className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-xl">
        <header className="flex items-center justify-between gap-3 border-b border-border p-4 sm:p-5">
          <div><h2 className="font-bold">انتخاب تصویر {pickerTarget === "desktop" ? "دسکتاپ" : "موبایل"}</h2><p className="mt-1 text-xs text-muted-foreground">تصویر انتخابی بدون کپی‌کردن فایل اصلی به بنر متصل می‌شود.</p></div>
          <button type="button" className={secondary} onClick={() => setPickerTarget(null)}>بستن</button>
        </header>
        <form className="flex gap-2 border-b border-border p-4" onSubmit={event => { event.preventDefault(); if (pickerQuery.trim().length === 1) { setPickerError("برای جستجو حداقل دو نویسه وارد کنید."); return; } if (pickerQuery.trim() !== pickerAppliedQuery || pickerPage !== 1) setPickerLoading(true); setPickerPage(1); setPickerAppliedQuery(pickerQuery.trim()); }}>
          <input value={pickerQuery} onChange={event => setPickerQuery(event.target.value)} placeholder="جستجوی نام محصول، رنگ، بنر یا متن جایگزین" className={field + " mt-0 min-w-0 flex-1"} />
          <button type="submit" className={primary}>جستجو</button>
        </form>
        {pickerError && <p role="alert" className="mx-4 mt-3 rounded-lg border border-destructive/40 p-3 text-sm">{pickerError}</p>}
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {pickerLoading ? <p className="py-12 text-center text-sm text-muted-foreground">در حال دریافت تصاویر…</p> :
            pickerItems.length === 0 ? <p className="py-12 text-center text-sm text-muted-foreground">تصویری برای انتخاب پیدا نشد.</p> :
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {pickerItems.map(item => <button key={item.id} type="button" onClick={() => chooseLibraryImage(item)} className="overflow-hidden rounded-xl border border-border text-right transition hover:border-primary hover:bg-muted">
                <div className="relative aspect-[4/3] bg-muted"><Image src={item.thumbnail_url || item.url} alt={item.alt_text || item.title} fill sizes="(max-width: 640px) 50vw, 25vw" unoptimized className="object-cover" /></div>
                <div className="p-3"><p className="line-clamp-1 text-sm font-semibold">{item.title}</p><p className="mt-1 text-xs text-muted-foreground">{item.source_label}</p><p className="mt-1 line-clamp-1 text-[11px] text-muted-foreground">{item.owner_label}</p></div>
              </button>)}
            </div>}
        </div>
        <footer className="flex items-center justify-between border-t border-border p-3">
          <button type="button" disabled={pickerPage <= 1 || pickerLoading} onClick={() => { setPickerLoading(true); setPickerPage(value => value - 1); }} className={secondary}>صفحه قبل</button>
          <span className="text-xs text-muted-foreground">{pickerCount.toLocaleString("fa-IR")} تصویر · صفحه {pickerPage.toLocaleString("fa-IR")}</span>
          <button type="button" disabled={pickerPage * 24 >= pickerCount || pickerLoading} onClick={() => { setPickerLoading(true); setPickerPage(value => value + 1); }} className={secondary}>صفحه بعد</button>
        </footer>
      </section>
    </div>}
  </main>;
}
