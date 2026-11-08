import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SignInForm } from "@/components/auth/SignInForm";
import { isLocale } from "@/i18n/config";
import { getAuthDictionary } from "@/i18n/dictionaries/auth";
import { safeRedirectPath } from "@/lib/auth/redirect";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<{ next?: string | string[] }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> {
 const { locale } = await params;
 if (!isLocale(locale)) return {};
 return { title: getAuthDictionary(locale).title, robots: { index: false, follow: false } };
}
export default async function SignInPage({ params, searchParams }: Props) {
 const { locale } = await params;
 if (!isLocale(locale)) notFound();
 const { next } = await searchParams;
 const t = getAuthDictionary(locale);
 return <div className="relative isolate flex min-h-[calc(100svh-5rem)] items-center justify-center overflow-hidden px-4 py-12 sm:py-16">
  <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
   <div className="absolute -start-32 top-1/4 size-72 rounded-full bg-foreground/[.035] blur-3xl sm:size-96" />
   <div className="absolute -end-32 bottom-0 size-80 rounded-full bg-foreground/[.04] blur-3xl sm:size-[28rem]" />
  </div>
  <div className="w-full max-w-5xl overflow-hidden rounded-[2rem] border border-border bg-card/90 shadow-[0_24px_90px_-42px_rgba(0,0,0,.24)] backdrop-blur-xl md:grid md:grid-cols-[.9fr_1.1fr]">
   <aside className="relative hidden min-h-[620px] flex-col justify-between overflow-hidden bg-foreground p-10 text-background md:flex">
    <div className="text-2xl font-black tracking-tight">ودزمانی<span className="text-background/45">.</span></div>
    <div className="relative z-10">
     <p className="mb-4 text-xs font-semibold tracking-[.22em] text-background/55">تجربه‌ای شخصی‌تر از خرید</p>
     <h2 className="max-w-sm text-4xl font-semibold leading-[1.35]">استایل خودت را، با خیال راحت انتخاب کن.</h2>
     <p className="mt-5 max-w-xs text-sm leading-8 text-background/65">به حساب کاربری‌ات وارد شو و تجربه خریدت را ساده‌تر ادامه بده.</p>
    </div>
    <div className="absolute -bottom-28 -end-24 size-80 rounded-full border border-background/10" />
    <div className="absolute -bottom-16 -end-12 size-56 rounded-full border border-background/10" />
    <div className="text-xs text-background/45">ودزمانی · استایل شخصی</div>
   </aside>
   <div className="flex min-h-[580px] items-center justify-center px-6 py-10 sm:px-10 md:px-12"><SignInForm locale={locale} t={t} redirectTo={safeRedirectPath(next, locale)} /></div>
  </div>
 </div>;
}
