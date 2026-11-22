"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type ThemeSettings = {
  primary: string;
  primary_foreground: string;
  accent: string;
  accent_foreground: string;
  font: "system" | "persian-modern" | "classic";
  radius: "compact" | "medium" | "rounded";
  motion: "none" | "subtle" | "standard";
};
type ThemeRevision = { id: number; action: "baseline" | "draft_saved" | "published" | "rollback"; snapshot: { draft_settings: ThemeSettings; published_settings: ThemeSettings }; created_by_label: string; created_at: string };
type ThemeResponse = {
  draft_settings: ThemeSettings;
  published_settings: ThemeSettings;
  published_at: string | null;
};
const defaults: ThemeSettings = {
  primary: "#171717",
  primary_foreground: "#fafafa",
  accent: "#e5e5e5",
  accent_foreground: "#171717",
  font: "system",
  radius: "medium",
  motion: "standard",
};
const presets: { name: string; settings: Pick<ThemeSettings, "primary" | "primary_foreground" | "accent" | "accent_foreground"> }[] = [
  { name: "مینیمال", settings: { primary: "#171717", primary_foreground: "#ffffff", accent: "#e5e5e5", accent_foreground: "#171717" } },
  { name: "آبی آرام", settings: { primary: "#315b78", primary_foreground: "#ffffff", accent: "#dceaf2", accent_foreground: "#18364b" } },
  { name: "سبز زیتونی", settings: { primary: "#59634a", primary_foreground: "#ffffff", accent: "#e7eadf", accent_foreground: "#343b2b" } },
  { name: "زرشکی", settings: { primary: "#783d4d", primary_foreground: "#ffffff", accent: "#f0e2e5", accent_foreground: "#4a2630" } },
];
const field = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm";
const button = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";

function errorMessage(error: unknown) {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "دسترسی لازم برای مدیریت قالب را ندارید.";
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "عملیات انجام نشد. اطلاعات را بررسی و دوباره تلاش کنید.";
}

export default function StorefrontThemePage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [draft, setDraft] = useState<ThemeSettings>(defaults);
  const [published, setPublished] = useState<ThemeSettings>(defaults);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [revisions, setRevisions] = useState<ThemeRevision[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiRequest<ThemeResponse>("GET", "/api/admin/storefront/theme/");
      setDraft(data.draft_settings);
      setPublished(data.published_settings);
      setError("");
    } catch (e) { setError(errorMessage(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    let active = true;
    void apiRequest<ThemeResponse>("GET", "/api/admin/storefront/theme/").then(data => {
      if (!active) return;
      setDraft(data.draft_settings);
      setPublished(data.published_settings);
    }).catch(e => { if (active) setError(errorMessage(e)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  function update<K extends keyof ThemeSettings>(key: K, value: ThemeSettings[K]) {
    setDraft(current => ({ ...current, [key]: value }));
  }

  async function saveDraft() {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest("PATCH", "/api/admin/storefront/theme/", { settings: draft });
      setNotice("پیش‌نویس قالب ذخیره شد؛ هنوز روی فروشگاه اعمال نشده است.");
      await refresh();
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  async function publish() {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest("PATCH", "/api/admin/storefront/theme/", { settings: draft });
      await apiRequest("POST", "/api/admin/storefront/theme/", { action: "publish" });
      setPublished(draft);
      setNotice("قالب جدید منتشر شد و در ویترین فروشگاه اعمال می‌شود.");
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  async function toggleHistory() {
    if (historyOpen) { setHistoryOpen(false); return; }
    setHistoryOpen(true); setHistoryLoading(true); setError("");
    try {
      const rows = await apiRequest<ThemeRevision[]>("GET", "/api/admin/storefront/theme/revisions/");
      setRevisions(rows);
    } catch (e) { setError(errorMessage(e)); }
    finally { setHistoryLoading(false); }
  }

  async function rollback(revision: ThemeRevision) {
    if (!window.confirm("تنظیمات پیش‌نویس با این نسخه جایگزین شود؟ قالب منتشرشده فعلی بدون تغییر می‌ماند.")) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<{ draft_settings: ThemeSettings; published_settings: ThemeSettings }>(
        "POST", "/api/admin/storefront/theme/revisions/", { revision_id: revision.id },
      );
      setDraft(result.draft_settings);
      setPublished(result.published_settings);
      setNotice("نسخه به پیش‌نویس بازگردانی شد. برای اعمال روی فروشگاه باید جداگانه منتشرش کنید.");
      const rows = await apiRequest<ThemeRevision[]>("GET", "/api/admin/storefront/theme/revisions/");
      setRevisions(rows);
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  const previewStyle = {
    "--preview-primary": draft.primary,
    "--preview-primary-foreground": draft.primary_foreground,
    "--preview-accent": draft.accent,
    "--preview-accent-foreground": draft.accent_foreground,
    borderRadius: draft.radius === "compact" ? "8px" : draft.radius === "rounded" ? "24px" : "14px",
    fontFamily: draft.font === "classic" ? '"Noto Naskh Arabic", Tahoma, serif' : draft.font === "persian-modern" ? 'Tahoma, "Noto Sans Arabic", sans-serif' : 'system-ui, Tahoma, sans-serif',
  } as CSSProperties;

  return <main dir="rtl" className="mx-auto w-full max-w-6xl px-4 py-8 sm:py-10">
    <div className="mb-7">
      <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
      <h1 className="mt-3 text-2xl font-bold sm:text-3xl">شخصی‌سازی ظاهر فروشگاه</h1>
      <p className="mt-2 text-sm leading-7 text-muted-foreground">قالب را تغییر دهید، پیش‌نمایش بگیرید و پس از تأیید منتشر کنید. تغییرات پیش‌نویس روی فروشگاه عمومی اعمال نمی‌شوند.</p>
    </div>
    {notice && <p role="status" className="mb-4 rounded-xl border border-border bg-muted p-3 text-sm">{notice}</p>}
    {error && <p role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</p>}
    {loading ? <p className="py-16 text-center text-sm text-muted-foreground">در حال دریافت تنظیمات قالب…</p> : <div className="grid gap-6 lg:grid-cols-2">
      <section className="space-y-5 rounded-2xl border border-border bg-card p-5">
        <div><h2 className="font-bold">قالب‌های آماده رنگ</h2><p className="mt-1 text-xs text-muted-foreground">انتخاب قالب فقط پیش‌نویس را تغییر می‌دهد.</p>
          <div className="mt-3 flex flex-wrap gap-2">{presets.map(preset => <button key={preset.name} type="button" className={button} onClick={() => setDraft(current => ({ ...current, ...preset.settings }))}>{preset.name}</button>)}</div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {([
            ["primary", "رنگ اصلی"],
            ["primary_foreground", "متن روی رنگ اصلی"],
            ["accent", "رنگ مکمل"],
            ["accent_foreground", "متن روی رنگ مکمل"],
          ] as const).map(([key, label]) => <label key={key} className="block text-sm">{label}<div className="mt-1 flex items-center gap-2"><input aria-label={label} type="color" value={draft[key]} onChange={e => update(key, e.target.value)} className="h-11 w-14 cursor-pointer rounded-lg border border-border bg-background p-1" /><input dir="ltr" value={draft[key]} onChange={e => update(key, e.target.value)} className={field} maxLength={7} /></div></label>)}
        </div>
        <label className="block text-sm">فونت فروشگاه<select value={draft.font} onChange={e => update("font", e.target.value as ThemeSettings["font"])} className={field}><option value="system">سیستمی</option><option value="persian-modern">فارسی مدرن</option><option value="classic">کلاسیک</option></select></label>
        <label className="block text-sm">گردی گوشه‌ها<select value={draft.radius} onChange={e => update("radius", e.target.value as ThemeSettings["radius"])} className={field}><option value="compact">کم</option><option value="medium">متوسط</option><option value="rounded">زیاد</option></select></label>
        <label className="block text-sm">حرکت و انیمیشن<select value={draft.motion} onChange={e => update("motion", e.target.value as ThemeSettings["motion"])} className={field}><option value="none">بدون انیمیشن</option><option value="subtle">ملایم</option><option value="standard">استاندارد</option></select></label>
        <div className="flex flex-wrap gap-2 pt-2"><button type="button" disabled={saving} onClick={() => void saveDraft()} className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold disabled:opacity-50">{saving ? "در حال ذخیره…" : "ذخیره پیش‌نویس"}</button><button type="button" disabled={saving} onClick={() => void publish()} className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50">انتشار قالب</button></div>
      </section>
      <section className="space-y-4">
        <div className="rounded-2xl border border-border bg-card p-5">
          <h2 className="font-bold">پیش‌نمایش زنده</h2><p className="mt-1 text-xs text-muted-foreground">این پیش‌نمایش محلی است و تا زمان انتشار، ظاهر فروشگاه را تغییر نمی‌دهد.</p>
          <div style={previewStyle} className="mt-4 overflow-hidden border border-border bg-background text-foreground">
            <div className="flex items-center justify-between border-b border-border p-4"><span className="font-bold">ودزمانی | Vedzmani</span><span className="text-xs">محصولات　 دسته‌بندی‌ها</span></div>
            <div className="p-5 sm:p-7" style={{ backgroundColor: "var(--preview-accent)", color: "var(--preview-accent-foreground)" }}>
              <p className="text-xs opacity-75">مجموعه جدید</p><h3 className="mt-2 text-2xl font-bold">استایل روزمره، انتخاب همیشگی</h3><p className="mt-2 text-sm">پیش‌نمایش رنگ، فونت و شکل اجزای فروشگاه</p>
              <button type="button" className="mt-4 px-4 py-2 text-sm font-semibold" style={{ backgroundColor: "var(--preview-primary)", color: "var(--preview-primary-foreground)", borderRadius: "inherit" }}>مشاهده محصولات</button>
            </div>
            <div className="grid grid-cols-2 gap-3 p-4"><div className="rounded-xl border border-border p-3"><div className="aspect-square rounded-lg bg-muted" /><p className="mt-2 text-sm font-semibold">محصول نمونه</p><p className="mt-1 text-xs text-muted-foreground">۲,۴۵۰,۰۰۰ تومان</p></div><div className="rounded-xl border border-border p-3"><div className="aspect-square rounded-lg bg-muted" /><p className="mt-2 text-sm font-semibold">محصول نمونه</p><p className="mt-1 text-xs text-muted-foreground">۱,۹۸۰,۰۰۰ تومان</p></div></div>
          </div>
        </div>
        <div className="rounded-2xl border border-border bg-card p-5"><h2 className="font-bold">قالب منتشرشده فعلی</h2><div className="mt-3 flex flex-wrap gap-2">{[published.primary,published.primary_foreground,published.accent,published.accent_foreground].map((color,index)=><span key={index} title={color} className="size-9 rounded-lg border border-border" style={{backgroundColor:color}} />)}</div><p className="mt-2 text-xs text-muted-foreground">رنگ اصلی منتشرشده: <span dir="ltr">{published.primary}</span></p></div>
        <div className="rounded-2xl border border-border bg-card p-5">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold">تاریخچه نسخه‌های قالب</h2><p className="mt-1 text-xs text-muted-foreground">بازگردانی فقط پیش‌نویس را تغییر می‌دهد؛ انتشار نیازمند تأیید جداگانه است.</p></div><button type="button" disabled={saving} onClick={() => void toggleHistory()} className={button}>{historyOpen ? "بستن تاریخچه" : "نمایش تاریخچه"}</button></div>
          {historyOpen && <div className="mt-4 space-y-2">
            {historyLoading ? <p className="text-xs text-muted-foreground">در حال دریافت تاریخچه…</p> : revisions.length === 0 ? <p className="text-xs text-muted-foreground">نسخه‌ای ثبت نشده است.</p> : revisions.map((revision, index) => <div key={revision.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted/50 p-3">
              <div><p className="text-sm font-medium">{revision.action === "baseline" ? "نسخه پایه" : revision.action === "draft_saved" ? "ذخیره پیش‌نویس" : revision.action === "published" ? "انتشار قالب" : "بازگردانی"}</p><p className="mt-1 text-xs text-muted-foreground">{revision.snapshot.draft_settings.primary} · {new Date(revision.created_at).toLocaleString("fa-IR")} · {revision.created_by_label}</p></div>
              {index > 0 && <button type="button" disabled={saving} onClick={() => void rollback(revision)} className={button}>بازگردانی به پیش‌نویس</button>}
            </div>)}
          </div>}
        </div>
      </section>
    </div>}
  </main>;
}
