"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/browser-api";

type Message = { id:number; body:string; is_internal:boolean; sender_is_staff:boolean; created_at:string };
type Ticket = { id:number; subject:string; category:string; status:string; created_at:string; updated_at:string; messages?:Message[] };
const statusLabels:Record<string,string>={open:"ثبت‌شده",in_progress:"در حال بررسی",waiting_customer:"منتظر پاسخ شما",resolved:"پاسخ داده‌شده",closed:"بسته‌شده"};
const dateFormat=new Intl.DateTimeFormat("fa-IR",{dateStyle:"medium",timeStyle:"short"});
const field="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm";

export function SupportTickets() {
 const [rows,setRows]=useState<Ticket[]>([]); const [selected,setSelected]=useState<Ticket|null>(null);
 const [subject,setSubject]=useState(""); const [category,setCategory]=useState("other"); const [body,setBody]=useState("");
 const [reply,setReply]=useState(""); const [creating,setCreating]=useState(false); const [error,setError]=useState(""); const [loading,setLoading]=useState(true);
 const load=useCallback(async()=>{setLoading(true);try{const data=await apiRequest<{results:Ticket[]}>("GET","/api/auth/support/tickets/");setRows(data.results);setSelected(current=>current?data.results.find(t=>t.id===current.id)??null:null);}catch{setError("دریافت درخواست‌های پشتیبانی ناموفق بود.");}finally{setLoading(false);}},[]);
 useEffect(()=>{void Promise.resolve().then(load);},[load]);
 async function open(t:Ticket){try{setSelected(await apiRequest<Ticket>("GET",`/api/auth/support/tickets/${t.id}/`));}catch{setError("دریافت گفت‌وگو ناموفق بود.");}}
 async function create(){if(!subject.trim()||!body.trim())return;setCreating(true);setError("");try{const t=await apiRequest<Ticket>("POST","/api/auth/support/tickets/",{subject:subject.trim(),category,message:body.trim()});setSubject("");setBody("");setSelected(t);await load();}catch{setError("ثبت درخواست انجام نشد. دوباره تلاش کنید.");}finally{setCreating(false);}}
 async function send(){if(!selected||!reply.trim())return;try{const t=await apiRequest<Ticket>("POST",`/api/auth/support/tickets/${selected.id}/`,{message:reply.trim()});setSelected(t);setReply("");await load();}catch{setError("ارسال پیام انجام نشد. ممکن است تیکت بسته شده باشد.");}}
 return <section className="space-y-5">
  <div><h2 className="text-xl font-bold">پشتیبانی و درخواست‌ها</h2><p className="mt-2 text-sm leading-7 text-muted-foreground">برای پیگیری سفارش، ارسال یا سایر موارد، درخواست ثبت کنید. پاسخ‌ها در همین بخش نمایش داده می‌شوند.</p></div>
  {error&&<p role="alert" className="rounded-xl border border-destructive/40 p-3 text-sm">{error}</p>}
  <div className="grid gap-4 lg:grid-cols-[minmax(220px,.8fr)_minmax(0,1.2fr)]">
   <div className="space-y-3">
    <div className="rounded-2xl border border-border p-4"><h3 className="font-semibold">ثبت درخواست جدید</h3><input className={field+" mt-3"} value={subject} maxLength={160} onChange={e=>setSubject(e.target.value)} placeholder="موضوع درخواست"/><select className={field+" mt-2"} value={category} onChange={e=>setCategory(e.target.value)}><option value="order">سفارش</option><option value="shipping">ارسال</option><option value="product">محصول</option><option value="payment">پرداخت</option><option value="other">سایر</option></select><textarea className={field+" mt-2 min-h-24"} value={body} maxLength={5000} onChange={e=>setBody(e.target.value)} placeholder="شرح درخواست…"/><button disabled={creating||!subject.trim()||!body.trim()} onClick={()=>void create()} className="mt-3 w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50">{creating?"در حال ثبت…":"ثبت درخواست"}</button></div>
    <div className="overflow-hidden rounded-2xl border border-border"><h3 className="border-b border-border p-3 text-sm font-semibold">درخواست‌های قبلی</h3>{loading?<p className="p-5 text-center text-xs text-muted-foreground">در حال دریافت…</p>:rows.length===0?<p className="p-5 text-center text-xs text-muted-foreground">هنوز درخواستی ثبت نکرده‌اید.</p>:rows.map(t=><button key={t.id} onClick={()=>void open(t)} className={`block w-full border-b border-border p-3 text-right last:border-0 hover:bg-muted/60 ${selected?.id===t.id?"bg-muted":""}`}><div className="flex justify-between gap-2"><strong className="text-sm">{t.subject}</strong><span className="text-[11px] text-muted-foreground">#{t.id}</span></div><p className="mt-1 text-xs text-muted-foreground">{statusLabels[t.status]??t.status} · {dateFormat.format(new Date(t.updated_at))}</p></button>)}</div>
   </div>
   <div className="rounded-2xl border border-border p-4">{!selected?<p className="py-12 text-center text-sm text-muted-foreground">یک درخواست را برای مشاهده گفت‌وگو انتخاب کنید.</p>:<><div className="border-b border-border pb-3"><h3 className="font-bold">{selected.subject}</h3><p className="mt-1 text-xs text-muted-foreground">وضعیت: {statusLabels[selected.status]??selected.status}</p></div><div className="my-4 max-h-96 space-y-3 overflow-y-auto">{(selected.messages??[]).map(m=><article key={m.id} className="rounded-xl bg-muted/60 p-3"><p className="mb-2 text-xs text-muted-foreground">{m.sender_is_staff?"پشتیبانی ودزمانی":"شما"} · {dateFormat.format(new Date(m.created_at))}</p><p className="whitespace-pre-wrap text-sm leading-7">{m.body}</p></article>)}</div>{["resolved","closed"].includes(selected.status)?<p className="rounded-xl bg-muted p-3 text-xs text-muted-foreground">این درخواست بسته شده است. برای موضوع جدید، درخواست تازه‌ای ثبت کنید.</p>:<><textarea className={field+" min-h-24"} value={reply} onChange={e=>setReply(e.target.value)} maxLength={5000} placeholder="پیام جدید…"/><button disabled={!reply.trim()} onClick={()=>void send()} className="mt-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50">ارسال پیام</button></>}</>}</div>
  </div>
 </section>;
}
