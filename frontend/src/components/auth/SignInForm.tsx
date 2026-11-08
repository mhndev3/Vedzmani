"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { localeMeta, type Locale } from "@/i18n/config";
import type { AuthDictionary } from "@/i18n/dictionaries/auth";
import { authApi } from "@/lib/auth/api";
import { classifyAuthError } from "@/lib/auth/errors";
import { fill } from "@/lib/format";

type Mode = "signup" | "login";
type Step = "phone" | "code" | "password" | "done";
const inputClass = "h-14 w-full rounded-2xl border border-border bg-background/80 px-4 text-base outline-none transition duration-200 placeholder:text-muted-foreground/65 focus:border-foreground focus:ring-4 focus:ring-foreground/5 disabled:opacity-60";
const primaryButton = "inline-flex h-14 w-full items-center justify-center rounded-2xl bg-foreground px-5 text-sm font-semibold text-background transition duration-200 hover:opacity-85 active:scale-[.99] disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButton = "text-sm font-medium text-muted-foreground underline-offset-4 transition hover:text-foreground hover:underline";
const iconButton = "absolute inset-y-0 end-3 my-auto rounded-lg p-2 text-muted-foreground transition hover:text-foreground";
const RESEND_COOLDOWN_SECONDS = 60;

export function SignInForm({ locale, t, redirectTo }: { locale: Locale; t: AuthDictionary; redirectTo: string }) {
 const router = useRouter();
 const [mode,setMode]=useState<Mode>("signup");
 const [step,setStep]=useState<Step>("phone");
 const [phone,setPhone]=useState("");
 const [code,setCode]=useState("");
 const [password,setPassword]=useState("");
 const [confirmPassword,setConfirmPassword]=useState("");
 const [showPassword,setShowPassword]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState<string|null>(null);
 const [banner,setBanner]=useState<string|null>(null);
 const [resent,setResent]=useState(false);
 const [resetting,setResetting]=useState(false);
 const [cooldownUntil,setCooldownUntil]=useState<number|null>(null);
 const [now,setNow]=useState(0);
 const inFlight=useRef(false);
 const alive=useRef(true);
 const phoneInput=useRef<HTMLInputElement>(null);
 const codeInput=useRef<HTMLInputElement>(null);
 const remaining=cooldownUntil===null?0:Math.max(0,Math.ceil((cooldownUntil-now)/1000));
 const numberFormat=new Intl.NumberFormat(localeMeta[locale].numberLocale);

 useEffect(()=>{ alive.current=true; authApi.me().then(async user=>{ if(!user||!alive.current)return; const checkout="/"+locale+"/checkout"; const isCheckout=redirectTo===checkout||redirectTo.startsWith(checkout+"?"); if(isCheckout){router.replace(redirectTo);return;} const profile=await authApi.profile().catch(()=>null); if(!alive.current)return; router.replace(profile?.is_complete?redirectTo:"/"+locale+"/profile?next="+encodeURIComponent(redirectTo)); }).catch(()=>{}); return ()=>{alive.current=false;}; },[router,redirectTo,locale]);
 useEffect(()=>{if(cooldownUntil===null)return;const id=setInterval(()=>{const value=Date.now();setNow(value);if(value>=cooldownUntil)setCooldownUntil(null);},1000);return()=>clearInterval(id);},[cooldownUntil]);
 useEffect(()=>{if(step==="phone")phoneInput.current?.focus();if(step==="code")codeInput.current?.focus();},[step]);
 function startCooldown(seconds:number){const value=Date.now();setNow(value);setCooldownUntil(value+seconds*1000);}
 function clearMessages(){setError(null);setBanner(null);setResent(false);}
 function errorMessage(e:unknown){const c=classifyAuthError(e);if(c.key==="rate_limited"&&c.retryAfterSeconds){const [unit,value]=c.retryAfterSeconds<60?["second",c.retryAfterSeconds] as const:["minute",Math.ceil(c.retryAfterSeconds/60)] as const;const wait=new Intl.NumberFormat(localeMeta[locale].numberLocale,{style:"unit",unit,unitDisplay:"long"}).format(value);return fill(t.errors.rate_limitedWait,{time:wait});}return t.errors[c.key];}
 async function finish(forceProfile=false){const checkout="/"+locale+"/checkout";const isCheckout=redirectTo===checkout||redirectTo.startsWith(checkout+"?");let destination=redirectTo;try{if(await authApi.me()===null){setBanner(t.errors.no_session);return;}if(!isCheckout){const profile=await authApi.profile();if(forceProfile||!profile.is_complete)destination="/"+locale+"/profile?next="+encodeURIComponent(redirectTo);}}catch{if(!isCheckout)destination="/"+locale+"/profile?next="+encodeURIComponent(redirectTo);}if(!alive.current)return;setStep("done");router.replace(destination);}
 async function sendCode(resend=false){if(inFlight.current)return;if(!phone.trim()){setError(t.required.phone);phoneInput.current?.focus();return;}inFlight.current=true;setBusy(true);clearMessages();try{await authApi.requestOtp(phone.trim());if(!alive.current)return;setCode("");setStep("code");startCooldown(RESEND_COOLDOWN_SECONDS);setResent(resend);}catch(e){if(!alive.current)return;setError(errorMessage(e));}finally{inFlight.current=false;if(alive.current)setBusy(false);}}
 async function verify(){if(inFlight.current)return;if(!code.trim()){setError(t.required.code);return;}inFlight.current=true;setBusy(true);clearMessages();try{const result=await authApi.verifyOtp(phone.trim(),code.trim());if(resetting||result.isNewUser){setStep("password");return;}await finish();}catch(e){if(!alive.current)return;setError(errorMessage(e));}finally{inFlight.current=false;if(alive.current)setBusy(false);}}
 async function submitPassword(){if(inFlight.current)return;if(!password){setError(t.required.password);return;}if(password!==confirmPassword){setError(t.password.mismatch);return;}inFlight.current=true;setBusy(true);clearMessages();try{await authApi.setPassword(password);await finish();}catch(e){if(alive.current)setError(errorMessage(e));}finally{inFlight.current=false;if(alive.current)setBusy(false);}}
 async function login(event:FormEvent<HTMLFormElement>){event.preventDefault();if(inFlight.current)return;if(!phone.trim()){setError(t.required.phone);return;}if(!password){setError(t.required.password);return;}inFlight.current=true;setBusy(true);clearMessages();try{await authApi.login(phone.trim(),password);await finish();}catch(e){if(alive.current)setError(errorMessage(e));}finally{inFlight.current=false;if(alive.current)setBusy(false);}}
 function switchMode(next:Mode){setMode(next);setStep("phone");setPassword("");setConfirmPassword("");setCode("");setResetting(false);clearMessages();}
 function forgotPassword(){setResetting(true);setMode("signup");setStep("phone");setPassword("");setConfirmPassword("");clearMessages();}
 if(step==="done")return <section className="rounded-3xl border border-border bg-card p-8 text-center" role="status"><div className="mx-auto mb-5 grid size-14 place-items-center rounded-full bg-muted text-2xl">✓</div><h2 className="text-xl font-semibold">{t.done.title}</h2><p className="mt-2 text-sm text-muted-foreground">{t.done.body}</p><Link href={redirectTo} className={secondaryButton}>{t.done.continue}</Link></section>;

 return <section className="mx-auto w-full max-w-[440px]">
  <div className="mb-7 text-center">
   <div className="mx-auto mb-5 grid size-14 place-items-center rounded-2xl border border-border bg-card text-xl font-black tracking-tight shadow-sm">V.</div>
   <h1 className="text-2xl font-bold tracking-tight sm:text-[28px]">{step==="password"?t.password.newTitle:resetting?"بازیابی رمز عبور":t.title}</h1>
   <p className="mx-auto mt-2 max-w-sm text-sm leading-7 text-muted-foreground">{step==="password"?t.password.newHint:resetting?"شماره موبایل خود را تأیید کنید تا رمز تازه‌ای بسازید.":t.intro}</p>
  </div>
  {step==="phone"&&mode==="login"&&!resetting?(
   <form onSubmit={login} noValidate className="auth-step grid gap-4" aria-busy={busy}>
    <div className="grid gap-2"><label htmlFor="auth-phone" className="text-sm font-medium">{t.phone.label}</label><input id="auth-phone" ref={phoneInput} className={inputClass+" text-start"} dir="ltr" type="tel" inputMode="tel" autoComplete="tel" placeholder="09123456789" maxLength={32} value={phone} disabled={busy} onChange={e=>{setPhone(e.target.value);setError(null);}}/></div>
    <div className="grid gap-2"><label htmlFor="auth-password" className="text-sm font-medium">{t.password.label}</label><div className="relative"><input id="auth-password" className={inputClass+" pe-16 text-start"} dir="ltr" type={showPassword?"text":"password"} autoComplete="current-password" value={password} disabled={busy} onChange={e=>{setPassword(e.target.value);setError(null);}}/><button type="button" className={iconButton} aria-label={showPassword?t.password.hide:t.password.show} onClick={()=>setShowPassword(v=>!v)}>{showPassword?"پنهان":"نمایش"}</button></div><button type="button" onClick={forgotPassword} className={"justify-self-start "+secondaryButton}>{t.password.forgot}</button></div>
    {error&&<p role="alert" className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
    <button className={primaryButton} disabled={busy}>{busy?"در حال ورود…":t.password.submit}</button>
   </form>
  ):step==="phone"?(
   <form onSubmit={e=>{e.preventDefault();void sendCode(false);}} noValidate className="auth-step grid gap-4" aria-busy={busy}>
    <div className="grid gap-2"><label htmlFor="auth-phone" className="text-sm font-medium">{t.phone.label}</label><input id="auth-phone" ref={phoneInput} className={inputClass+" text-start"} dir="ltr" type="tel" inputMode="tel" autoComplete="tel" placeholder="09123456789" maxLength={32} value={phone} disabled={busy} onChange={e=>{setPhone(e.target.value);setError(null);}}/><p className="text-xs text-muted-foreground">{t.phone.hint}</p></div>
    {error&&<p role="alert" className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
    <button data-testid="auth-send-code" aria-label={busy?t.phone.submitting:t.phone.submit} className={primaryButton} disabled={busy}>{busy?<><span aria-hidden="true" className="me-2 size-4 animate-spin rounded-full border-2 border-current border-e-transparent" /><span role="status" aria-live="polite">{t.phone.submitting}</span></>:t.phone.submit}</button>
   </form>
  ):step==="code"?(
   <form onSubmit={e=>{e.preventDefault();void verify();}} noValidate className="auth-step grid gap-4" aria-busy={busy}>
    <p className="text-center text-sm leading-7 text-muted-foreground">{t.code.instruction.split("{phone}")[0]}<bdi dir="ltr" className="font-semibold text-foreground">{phone}</bdi>{t.code.instruction.split("{phone}")[1]}</p>
    <div className="grid gap-2"><label htmlFor="auth-code" className="text-sm font-medium">{t.code.label}</label><input id="auth-code" ref={codeInput} className={inputClass+" text-center tracking-[.45em]"} dir="ltr" type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={16} value={code} disabled={busy} onChange={e=>{setCode(e.target.value);setError(null);}}/><p className="text-xs text-muted-foreground">{t.code.hint}</p></div>
    {resent&&<p role="status" className="text-sm text-muted-foreground">{t.code.resent}</p>}
    {error&&<p role="alert" className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
    <button className={primaryButton} disabled={busy}>{busy?t.code.submitting:t.code.submit}</button>
    <div className="flex items-center justify-between"><button type="button" className={secondaryButton} disabled={busy||remaining>0} onClick={()=>void sendCode(true)}>{remaining>0?fill(t.code.resendIn,{seconds:numberFormat.format(remaining)}):t.code.resend}</button><button type="button" className={secondaryButton} disabled={busy} onClick={()=>{setStep("phone");setCode("");clearMessages();}}>{t.code.change}</button></div>
   </form>
  ):(
   <form onSubmit={e=>{e.preventDefault();void submitPassword();}} noValidate className="auth-step grid gap-4" aria-busy={busy}>
    <div className="grid gap-2"><label htmlFor="new-password" className="text-sm font-medium">{t.password.label}</label><div className="relative"><input id="new-password" className={inputClass+" pe-16 text-start"} dir="ltr" type={showPassword?"text":"password"} autoComplete="new-password" minLength={10} value={password} disabled={busy} onChange={e=>{setPassword(e.target.value);setError(null);}}/><button type="button" className={iconButton} onClick={()=>setShowPassword(v=>!v)}>{showPassword?"پنهان":"نمایش"}</button></div></div>
    <div className="grid gap-2"><label htmlFor="confirm-password" className="text-sm font-medium">{t.password.confirm}</label><input id="confirm-password" className={inputClass+" text-start"} dir="ltr" type={showPassword?"text":"password"} autoComplete="new-password" value={confirmPassword} disabled={busy} onChange={e=>{setConfirmPassword(e.target.value);setError(null);}}/></div>
    {error&&<p role="alert" className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
    <button className={primaryButton} disabled={busy}>{busy?t.password.creating:t.password.create}</button>
   </form>
  )}
  {step==="phone"&&!resetting&&<div className="mt-7 flex items-center justify-center gap-2 text-sm text-muted-foreground"><span>{mode==="signup"?t.modes.loginHint:t.modes.signupHint}</span><button type="button" className="font-semibold text-foreground underline underline-offset-4" onClick={()=>switchMode(mode==="signup"?"login":"signup")}>{mode==="signup"?t.modes.switchLogin:t.modes.switchSignup}</button></div>}
  <p className="mt-8 text-center text-xs leading-6 text-muted-foreground">با ادامه، شرایط استفاده و حریم خصوصی فروشگاه را می‌پذیرید.</p>
 </section>;
}
