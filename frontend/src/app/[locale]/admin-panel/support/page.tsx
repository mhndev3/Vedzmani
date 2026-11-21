"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Ticket = { id: number; subject: string; category: string; status: string; customer_id: number; created_at: string; updated_at: string; message_count?: number; messages?: { id: number; body: string; is_internal: boolean; sender_is_staff: boolean; created_at: string }[] };
const labels: Record<string,string> = { open:"باز", in_progress:"در حال بررسی", waiting_customer:"در انتظار مشتری", resolved:"حل‌شده", closed:"بسته" };
const categories: Record<string,string> = { order:"سفارش", shipping:"ارسال", product:"محصول", payment:"پرداخت", other:"سایر" };
const dateFormat = new Intl.DateTimeFormat("fa-IR", { dateStyle:"medium", timeStyle:"short" });
const inputClass = "w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm";

export default function AdminSupportPage() {
  const params = useParams<{locale:string}>();
  const locale = params.locale || "fa";
  const [rows,setRows] = useState<Ticket[]>([]);
  const [selected,setSelected] = useState<Ticket|null>(null);
  const [filter,setFilter] = useState("");
  const [message,setMessage] = useState("");
  const [internal,setInternal] = useState(false);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const query = filter ? "?status="+encodeURIComponent(filter) : "";
      const data = await apiRequest<{results:Ticket[]}>("GET","/api/admin/support/tickets/"+query);
      setRows(data.results);
      setSelected(current => current ? data.results.find(t=>t.id===current.id) ?? null : null);
    } catch (e) {
      setRows([]);
      setError(e instanceof BrowserApiError && e.status===403 ? "مجوز مشاهده تیکت‌های پشتیبانی برای حساب شما فعال نیست." : "دریافت تیکت‌ها با خطا مواجه شد.");
    } finally { setLoading(false); }
  },[filter]);

  useEffect(()=>{ void Promise.resolve().then(load); },[load]);

  async function openTicket(ticket:Ticket) {
    try { setSelected(await apiRequest<Ticket>("GET",`/api/admin/support/tickets/${ticket.id}/`)); }
    catch { setError("دریافت جزئیات تیکت ناموفق بود."); }
  }
  async function updateStatus(status:string) {
    if (!selected) return;
    try {
      const updated = await apiRequest<Ticket>("PATCH",`/api/admin/support/tickets/${selected.id}/`,{status});
      setSelected(updated); await load();
    } catch { setError("ذخیره وضعیت تیکت ناموفق بود."); }
  }
  async function sendMessage() {
    if (!selected || !message.trim()) return;
    try {
      const updated = await apiRequest<Ticket>("POST",`/api/admin/support/tickets/${selected.id}/`,{message:message.trim(),is_internal:internal});
      setSelected(updated); setMessage(""); await load();
    } catch { setError("ارسال پاسخ ناموفق بود."); }
  }

  return <main dir="rtl" className="mx-auto w-full max-w-7xl px-4 py-8 sm:py-10">
    <div className="mb-7"><Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link><h1 className="mt-3 text-2xl font-bold sm:text-3xl">پشتیبانی مشتریان</h1><p className="mt-2 text-sm text-muted-foreground">مدیریت درخواست‌ها، پاسخ‌گویی و پیگیری وضعیت تیکت‌ها</p></div>
    <div className="mb-5 flex flex-wrap gap-3"><select className={inputClass+" max-w-xs"} value={filter} onChange={e=>setFilter(e.target.value)}><option value="">همه وضعیت‌ها</option>{Object.entries(labels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select><button className="rounded-xl border border-border px-4 py-2 text-sm" onClick={()=>void load()}>به‌روزرسانی</button></div>
    {error && <p role="alert" className="mb-4 rounded-xl border border-destructive/40 p-3 text-sm">{error}</p>}
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(280px,.85fr)_minmax(0,1.15fr)]">
      <section className="overflow-hidden rounded-2xl border border-border bg-card"><h2 className="border-b border-border p-4 font-semibold">صندوق تیکت‌ها ({rows.length.toLocaleString("fa-IR")})</h2>{loading?<p className="p-8 text-center text-sm text-muted-foreground">در حال دریافت…</p>:rows.length===0?<p className="p-8 text-center text-sm text-muted-foreground">تیکتی برای نمایش وجود ندارد.</p>:<div className="divide-y divide-border">{rows.map(t=><button key={t.id} onClick={()=>void openTicket(t)} className={`block w-full p-4 text-right hover:bg-muted/60 ${selected?.id===t.id?"bg-muted":""}`}><div className="flex justify-between gap-2"><strong className="text-sm">{t.subject}</strong><span className="text-xs text-muted-foreground">#{t.id.toLocaleString("fa-IR")}</span></div><div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground"><span>{categories[t.category]??t.category}</span><span>·</span><span>{labels[t.status]??t.status}</span><span>·</span><span>حساب #{t.customer_id.toLocaleString("fa-IR")}</span></div><p className="mt-2 text-xs text-muted-foreground">{dateFormat.format(new Date(t.updated_at))}</p></button>)}</div>}</section>
      <section className="rounded-2xl border border-border bg-card p-4 sm:p-5">{!selected?<p className="py-12 text-center text-sm text-muted-foreground">برای مشاهده گفت‌وگو، یک تیکت را انتخاب کنید.</p>:<>
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4"><div><p className="text-xs text-muted-foreground">تیکت #{selected.id.toLocaleString("fa-IR")} · حساب مشتری #{selected.customer_id.toLocaleString("fa-IR")}</p><h2 className="mt-1 text-lg font-bold">{selected.subject}</h2></div><select aria-label="وضعیت تیکت" className={inputClass+" max-w-44"} value={selected.status} onChange={e=>void updateStatus(e.target.value)}>{Object.entries(labels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></div>
        <div className="my-4 max-h-[440px] space-y-3 overflow-y-auto">{(selected.messages??[]).map(m=><article key={m.id} className={`rounded-xl border p-3 ${m.is_internal?"border-amber-500/40 bg-amber-500/5":"border-border"}`}><div className="mb-2 flex flex-wrap justify-between gap-2 text-xs text-muted-foreground"><span>{m.is_internal?"یادداشت داخلی":m.sender_is_staff?"پاسخ پشتیبانی":"پیام مشتری"}</span><span>{dateFormat.format(new Date(m.created_at))}</span></div><p className="whitespace-pre-wrap text-sm leading-7">{m.body}</p></article>)}</div>
        <div className="space-y-3 border-t border-border pt-4"><textarea className={inputClass+" min-h-28"} value={message} maxLength={5000} onChange={e=>setMessage(e.target.value)} placeholder="متن پاسخ یا یادداشت داخلی…"/><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={internal} onChange={e=>setInternal(e.target.checked)}/> یادداشت داخلی (برای مشتری نمایش داده نشود)</label><button disabled={!message.trim()} onClick={()=>void sendMessage()} className="rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50">ثبت پیام</button></div>
      </>}</section>
    </div>
  </main>;
}
