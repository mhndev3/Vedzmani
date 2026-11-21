"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Method = {
  id: number; code: string; name: string; provider: "post" | "tipax" | "other";
  pricing_mode: "fixed" | "quote"; amount_toman: number | null; service_area: string;
  min_delivery_days: number | null; max_delivery_days: number | null; description: string;
  is_active: boolean; position: number;
};
type Page<T> = { results: T[]; next: string | null };
type Draft = Omit<Method, "id">;
const blank = (): Draft => ({
  code: "", name: "", provider: "post", pricing_mode: "quote", amount_toman: null,
  service_area: "", min_delivery_days: null, max_delivery_days: null,
  description: "", is_active: false, position: 0,
});
const inputClass = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm";
const primaryClass = "rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondaryClass = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";
const providerLabel = { post: "پست", tipax: "تیپاکس", other: "سایر" };
const money = (amount: number | null) => amount === null ? "نیازمند استعلام" : amount.toLocaleString("fa-IR") + " تومان";

function errorText(error: unknown) {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "مجوز مشاهده یا ویرایش روش‌های ارسال را ندارید.";
  if (error instanceof BrowserApiError && error.status === 400) return "اطلاعات واردشده معتبر نیست؛ مبلغ و بازه زمانی ارسال را بررسی کنید.";
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "ذخیره اطلاعات انجام نشد.";
}

export default function AdminShippingPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [methods, setMethods] = useState<Method[]>([]);
  const [draft, setDraft] = useState<Draft>(blank());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const rows: Method[] = [];
      let next: string | null = "/api/admin/shipping/methods/";
      let pages = 0;
      while (next && pages < 30) {
        const data: Page<Method> = await apiRequest<Page<Method>>("GET", next);
        rows.push(...data.results);
        if (!data.next) break;
        const url: URL = new URL(data.next, window.location.origin);
        next = url.pathname + url.search;
        pages += 1;
      }
      setMethods(rows);
    } catch (e) { setError(errorText(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void Promise.resolve().then(() => refresh()); }, [refresh]);

  function edit(method: Method) {
    const { id, ...values } = method;
    setEditingId(id);
    setDraft(values);
    setNotice("");
  }

  function reset() { setEditingId(null); setDraft(blank()); }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true); setError(""); setNotice("");
    try {
      const payload = { ...draft, amount_toman: draft.pricing_mode === "fixed" ? draft.amount_toman : null };
      if (editingId) await apiRequest("PATCH", "/api/admin/shipping/methods/" + editingId + "/", payload);
      else await apiRequest("POST", "/api/admin/shipping/methods/", payload);
      setNotice(editingId ? "روش ارسال به‌روزرسانی شد." : "روش ارسال ثبت شد.");
      reset();
      await refresh();
    } catch (e) { setError(errorText(e)); }
    finally { setSaving(false); }
  }

  async function toggle(method: Method) {
    setError(""); setNotice("");
    try {
      await apiRequest("PATCH", "/api/admin/shipping/methods/" + method.id + "/", { is_active: !method.is_active });
      setNotice(method.is_active ? "روش ارسال غیرفعال شد." : "روش ارسال فعال شد.");
      await refresh();
    } catch (e) { setError(errorText(e)); }
  }

  return (
    <main dir="rtl" className="mx-auto w-full max-w-6xl px-4 py-8 sm:py-10">
      <div className="mb-7">
        <Link href={"/" + locale + "/admin-panel"} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
        <h1 className="mt-3 text-2xl font-bold sm:text-3xl">مدیریت روش‌های ارسال</h1>
        <p className="mt-2 max-w-3xl text-sm leading-7 text-muted-foreground">تعریف شرکت حمل، محدوده سرویس‌دهی، تعرفه و زمان تقریبی تحویل. تا زمان تأیید تعرفه‌ها، روش‌ها به‌صورت پیش‌فرض غیرفعال ثبت می‌شوند.</p>
      </div>

      <div className="mb-5 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm leading-7">
        <strong>نکته مهم:</strong> این تنظیمات فعلاً فقط در پنل مدیریت ذخیره می‌شوند و به Checkout، مبلغ سفارش یا درگاه SEP متصل نیستند. هزینه پست و تیپاکس باید از شرکت‌ها تأیید شود و سپس در مرحله جداگانه به سفارش متصل شود.
      </div>

      {error && <div role="alert" className="mb-4 rounded-xl border border-destructive/40 p-3 text-sm">{error}</div>}
      {notice && <div role="status" className="mb-4 rounded-xl border border-border bg-muted p-3 text-sm">{notice}</div>}

      <form onSubmit={submit} className="mb-8 rounded-2xl border border-border bg-card p-4 sm:p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="font-semibold">{editingId ? "ویرایش روش ارسال" : "افزودن روش ارسال"}</h2>
          {editingId && <button type="button" className={secondaryClass} onClick={reset}>لغو ویرایش</button>}
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-sm">نام نمایشی<input required maxLength={100} className={inputClass} value={draft.name} onChange={e=>setDraft(v=>({...v,name:e.target.value}))} placeholder="مثلاً پست پیشتاز" /></label>
          <label className="text-sm">شناسه انگلیسی<input required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" maxLength={40} className={inputClass} value={draft.code} onChange={e=>setDraft(v=>({...v,code:e.target.value}))} placeholder="post-express" /></label>
          <label className="text-sm">شرکت حمل<select className={inputClass} value={draft.provider} onChange={e=>setDraft(v=>({...v,provider:e.target.value as Draft["provider"]}))}><option value="post">پست</option><option value="tipax">تیپاکس</option><option value="other">سایر</option></select></label>
          <label className="text-sm">نوع تعرفه<select className={inputClass} value={draft.pricing_mode} onChange={e=>setDraft(v=>({...v,pricing_mode:e.target.value as Draft["pricing_mode"],amount_toman:e.target.value==="quote"?null:v.amount_toman}))}><option value="quote">استعلام از شرکت حمل</option><option value="fixed">مبلغ ثابت</option></select></label>
          {draft.pricing_mode === "fixed" && <label className="text-sm">هزینه ارسال (تومان)<input required type="number" min="0" step="1" className={inputClass} value={draft.amount_toman ?? ""} onChange={e=>setDraft(v=>({...v,amount_toman:e.target.value===""?null:Number(e.target.value)}))} /></label>}
          <label className="text-sm">محدوده سرویس‌دهی<input maxLength={160} className={inputClass} value={draft.service_area} onChange={e=>setDraft(v=>({...v,service_area:e.target.value}))} placeholder="مثلاً سراسر ایران" /></label>
          <label className="text-sm">حداقل زمان تحویل (روز)<input type="number" min="0" max="365" className={inputClass} value={draft.min_delivery_days ?? ""} onChange={e=>setDraft(v=>({...v,min_delivery_days:e.target.value===""?null:Number(e.target.value)}))} /></label>
          <label className="text-sm">حداکثر زمان تحویل (روز)<input type="number" min="0" max="365" className={inputClass} value={draft.max_delivery_days ?? ""} onChange={e=>setDraft(v=>({...v,max_delivery_days:e.target.value===""?null:Number(e.target.value)}))} /></label>
          <label className="text-sm">ترتیب نمایش<input type="number" min="0" className={inputClass} value={draft.position} onChange={e=>setDraft(v=>({...v,position:Number(e.target.value)}))} /></label>
          <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={draft.is_active} onChange={e=>setDraft(v=>({...v,is_active:e.target.checked}))} /> فعال باشد (فقط برای پیکربندی؛ فعلاً در Checkout نمایش داده نمی‌شود)</label>
          <label className="text-sm sm:col-span-2 lg:col-span-3">توضیحات<textarea maxLength={500} rows={3} className={inputClass} value={draft.description} onChange={e=>setDraft(v=>({...v,description:e.target.value}))} /></label>
        </div>
        <button disabled={saving} className={primaryClass + " mt-5"}>{saving ? "در حال ذخیره…" : editingId ? "ذخیره تغییرات" : "ثبت روش ارسال"}</button>
      </form>

      <section className="rounded-2xl border border-border bg-card">
        <div className="border-b border-border p-4 font-semibold">روش‌های تعریف‌شده ({methods.length.toLocaleString("fa-IR")})</div>
        {loading ? <p className="p-8 text-center text-sm text-muted-foreground">در حال دریافت اطلاعات…</p> : methods.length === 0 ? <p className="p-8 text-center text-sm text-muted-foreground">هنوز روش ارسالی ثبت نشده است.</p> : (
          <div className="divide-y divide-border">
            {methods.map(method=><article key={method.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2"><strong>{method.name}</strong><span className="rounded-full bg-muted px-2 py-1 text-xs">{providerLabel[method.provider]}</span><span className="rounded-full bg-muted px-2 py-1 text-xs">{method.is_active?"فعال":"غیرفعال"}</span></div>
                <p className="mt-1 text-sm text-muted-foreground">{money(method.amount_toman)} · {method.service_area || "محدوده نامشخص"} · {method.min_delivery_days ?? "؟"} تا {method.max_delivery_days ?? "؟"} روز</p>
                {method.description && <p className="mt-1 text-xs text-muted-foreground">{method.description}</p>}
                <p className="mt-1 text-xs text-muted-foreground" dir="ltr">{method.code}</p>
              </div>
              <div className="flex shrink-0 gap-2">
                <button type="button" className={secondaryClass} onClick={()=>edit(method)}>ویرایش</button>
                <button type="button" className={secondaryClass} onClick={()=>void toggle(method)}>{method.is_active?"غیرفعال‌سازی":"فعال‌سازی"}</button>
              </div>
            </article>)}
          </div>
        )}
      </section>
    </main>
  );
}
