"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Event = { id:number; actor_id:number|null; actor_label:string; action:string; method:string; path:string; entity_type:string; entity_id:number|null; response_status:number; created_at:string };
type Result = { count:number; page:number; page_size:number; results:Event[] };
const labels:Record<string,string> = {post:"ایجاد",put:"جایگزینی",patch:"ویرایش",delete:"حذف"};
const dateFormat = new Intl.DateTimeFormat("fa-IR",{dateStyle:"medium",timeStyle:"short"});
const inputClass = "rounded-xl border border-border bg-background px-3 py-2.5 text-sm";

export default function AdminAuditLogPage() {
  const params=useParams<{locale:string}>(); const locale=params.locale||"fa";
  const [data,setData]=useState<Result>({count:0,page:1,page_size:50,results:[]});
  const [actor,setActor]=useState(""); const [action,setAction]=useState(""); const [entity,setEntity]=useState("");
  const [start,setStart]=useState(""); const [end,setEnd]=useState(""); const [page,setPage]=useState(1);
  const [loading,setLoading]=useState(true); const [error,setError]=useState("");
  const load=useCallback(async()=>{
    setLoading(true);setError("");
    const q=new URLSearchParams({page:String(page)});
    if(actor.trim())q.set("actor",actor.trim()); if(action)q.set("action",action);
    if(entity.trim())q.set("entity",entity.trim()); if(start)q.set("start",start); if(end)q.set("end",end);
    try{setData(await apiRequest<Result>("GET","/api/admin/audit-log/?"+q.toString()));}
    catch(e){setData({count:0,page,page_size:50,results:[]});setError(e instanceof BrowserApiError&&e.status===403?"مجوز مشاهده تاریخچه برای حساب شما فعال نیست.":"دریافت تاریخچه ناموفق بود.");}
    finally{setLoading(false);}
  },[page,actor,action,entity,start,end]);
  useEffect(()=>{void Promise.resolve().then(load);},[load]);
  const reset=()=>{setActor("");setAction("");setEntity("");setStart("");setEnd("");setPage(1);};
  return <main dir="rtl" className="mx-auto w-full max-w-7xl px-4 py-8 sm:py-10">
    <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
    <h1 className="mt-3 text-2xl font-bold sm:text-3xl">تاریخچه فعالیت مدیران</h1>
    <p className="mt-2 text-sm leading-7 text-muted-foreground">عملیات نوشتنی پنل مدیریت، زمان اجرا، مسیر و نتیجه درخواست</p>
    <section className="my-5 grid gap-3 rounded-2xl border border-border bg-card p-4 sm:grid-cols-2 lg:grid-cols-5">
      <input className={inputClass} inputMode="numeric" value={actor} onChange={e=>setActor(e.target.value)} placeholder="شناسه مدیر" aria-label="شناسه مدیر"/>
      <select className={inputClass} value={action} onChange={e=>setAction(e.target.value)} aria-label="نوع عملیات"><option value="">همه عملیات</option>{Object.entries(labels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select>
      <input className={inputClass} value={entity} onChange={e=>setEntity(e.target.value)} placeholder="نوع موجودیت" aria-label="نوع موجودیت"/>
      <input className={inputClass} type="date" value={start} onChange={e=>setStart(e.target.value)} aria-label="از تاریخ"/>
      <input className={inputClass} type="date" value={end} onChange={e=>setEnd(e.target.value)} aria-label="تا تاریخ"/>
      <button onClick={()=>{setPage(1);void Promise.resolve().then(load);}} className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground">اعمال فیلترها</button>
      <button onClick={reset} className="rounded-xl border border-border px-4 py-2.5 text-sm">پاک‌کردن فیلترها</button>
    </section>
    {error&&<p role="alert" className="mb-4 rounded-xl border border-destructive/40 p-3 text-sm">{error}</p>}
    <section className="overflow-hidden rounded-2xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border p-4"><h2 className="font-semibold">رویدادها</h2><span className="text-sm text-muted-foreground">{data.count.toLocaleString("fa-IR")} رویداد</span></div>
      {loading?<p className="p-10 text-center text-sm text-muted-foreground">در حال دریافت…</p>:!data.results.length?<p className="p-10 text-center text-sm text-muted-foreground">رویدادی برای نمایش وجود ندارد.</p>:
      <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-right text-sm"><thead className="bg-muted/50 text-muted-foreground"><tr>{["زمان","مدیر","عملیات","بخش","مسیر","نتیجه"].map(x=><th key={x} className="p-3 font-medium">{x}</th>)}</tr></thead><tbody className="divide-y divide-border">{data.results.map(e=><tr key={e.id}><td className="whitespace-nowrap p-3">{dateFormat.format(new Date(e.created_at))}</td><td className="p-3">{e.actor_label}</td><td className="p-3">{labels[e.action]||e.action}</td><td className="p-3">{e.entity_type}{e.entity_id?` #${e.entity_id.toLocaleString("fa-IR")}`:""}</td><td dir="ltr" className="max-w-[320px] truncate p-3 text-left text-xs">{e.path}</td><td className="p-3"><span className={e.response_status>=400?"text-destructive":"text-muted-foreground"}>{e.response_status}</span></td></tr>)}</tbody></table></div>}
      <div className="flex items-center justify-between border-t border-border p-4"><button disabled={page<=1||loading} onClick={()=>setPage(p=>Math.max(1,p-1))} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40">صفحه قبل</button><span className="text-xs text-muted-foreground">صفحه {page.toLocaleString("fa-IR")}</span><button disabled={page*data.page_size>=data.count||loading} onClick={()=>setPage(p=>p+1)} className="rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-40">صفحه بعد</button></div>
    </section>
    <p className="mt-4 text-xs leading-6 text-muted-foreground">متن درخواست، کوکی، نشانی IP، رمز، OTP، اطلاعات پرداخت و اطلاعات شخصی مشتری در لاگ ذخیره نمی‌شوند.</p>
  </main>;
}
