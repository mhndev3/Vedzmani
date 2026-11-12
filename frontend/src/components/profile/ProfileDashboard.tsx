"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import type { CustomerProfile } from "@/lib/auth/api";
import { authApi } from "@/lib/auth/api";
import { ProfileForm } from "./ProfileForm";
import { SavedProducts } from "./SavedProducts";
import { OrderHistory } from "./OrderHistory";
type Section = "orders" | "favorites" | "addresses" | "account";
const items: {id:Section;label:string;icon:string}[]=[{id:"orders",label:"سفارش‌ها",icon:"▣"},{id:"favorites",label:"علاقه‌مندی‌ها",icon:"♡"},{id:"addresses",label:"آدرس‌ها",icon:"⌖"},{id:"account",label:"اطلاعات حساب",icon:"ⓘ"}];
export function ProfileDashboard({profile:initial,locale,continueTo,t}:{profile:CustomerProfile;locale:Locale;continueTo:string;t:Dictionary}) {
 const [section,setSection]=useState<Section>("orders"); const [profile,setProfile]=useState(initial); const [loggingOut,setLoggingOut]=useState(false); const [error,setError]=useState(""); const router=useRouter();
 async function logout(){if(loggingOut)return;setLoggingOut(true);setError("");try{await authApi.logout();router.replace("/"+locale);router.refresh();}catch{setError("خروج از حساب انجام نشد. دوباره تلاش کنید.");setLoggingOut(false);}}
 return <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:py-10" dir="rtl"><div className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
  <header className="flex items-center gap-3 border-b border-border px-5 py-5 sm:px-7"><span className="grid size-12 shrink-0 place-items-center rounded-full bg-muted text-xl">♙</span><div className="min-w-0"><p className="truncate text-sm text-muted-foreground">{[profile.first_name,profile.last_name].filter(Boolean).join(" ")||"حساب کاربری شما"}</p><p className="mt-1 text-sm font-medium" dir="ltr">{profile.phone}</p></div><span className="mr-auto rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">{profile.is_complete?"حساب تکمیل‌شده":"تکمیل اطلاعات حساب"}</span></header>
  <div className="grid md:grid-cols-[220px_minmax(0,1fr)]"><nav aria-label="بخش‌های پروفایل" className="border-b border-border p-3 md:border-b-0 md:border-l md:p-4"><ul className="grid grid-cols-2 gap-2 md:grid-cols-1">{items.map(item=><li key={item.id}><button type="button" onClick={()=>setSection(item.id)} aria-current={section===item.id?"page":undefined} className={"flex min-h-12 w-full items-center gap-3 rounded-xl px-3 py-3 text-right text-sm transition "+(section===item.id?"bg-muted font-semibold text-foreground":"text-muted-foreground hover:bg-muted/60 hover:text-foreground")}><span className="w-5 text-center text-xl" aria-hidden="true">{item.icon}</span>{item.label}</button></li>)}<li className="col-span-2 border-t border-border pt-2 md:col-span-1"><button type="button" onClick={()=>void logout()} disabled={loggingOut} className="flex min-h-12 w-full items-center gap-3 rounded-xl px-3 py-3 text-right text-sm text-muted-foreground hover:bg-muted/60 hover:text-destructive disabled:opacity-60"><span className="w-5 text-center text-xl">⇥</span>{loggingOut?"در حال خروج…":"خروج از حساب"}</button></li></ul>{error&&<p role="alert" className="mt-2 px-2 text-xs text-destructive">{error}</p>}</nav>
  <main className="min-w-0 p-4 sm:p-6">{section==="orders"&&<OrderHistory/>}{section==="favorites"&&<SavedProducts locale={locale} t={t} />}{section==="addresses"&&<ProfileForm key="addresses" initialProfile={profile} locale={locale} continueTo={continueTo} mode="address" onProfileChange={setProfile} />}{section==="account"&&<ProfileForm key="account" initialProfile={profile} locale={locale} continueTo={continueTo} mode="account" onProfileChange={setProfile}/ >}</main></div>
 </div></div>;
}