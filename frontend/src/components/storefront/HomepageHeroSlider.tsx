"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Locale } from "@/i18n/config";

const slides = {
  fa: [
    { eyebrow: "VEDZMANI EDIT", title: "استایل تازه،\nانتخابِ تو", body: "برای روزهای معمولی، انتخاب‌های متفاوت پیدا کن.", cta: "مشاهده محصولات", tone: "rose" },
    { eyebrow: "YOUR EVERYDAY, REFINED", title: "جزئیات کوچک،\nتفاوت بزرگ", body: "انتخاب‌هایی برای ساختن استایلی که به خودت می‌آید.", cta: "کشف محصولات", tone: "sand" },
    { eyebrow: "THE NEW MOOD", title: "ساده انتخاب کن.\nمتفاوت دیده شو.", body: "نگاهی تازه به انتخاب‌های روزمره‌ات.", cta: "خرید و گشت‌وگذار", tone: "olive" },
  ],
  en: [
    { eyebrow: "VEDZMANI EDIT", title: "A fresh look,\nyour own way", body: "Find something different for the everyday.", cta: "Explore products", tone: "rose" },
    { eyebrow: "YOUR EVERYDAY, REFINED", title: "Small details.\nA big difference.", body: "Thoughtful picks for a style that feels like you.", cta: "Discover the edit", tone: "sand" },
    { eyebrow: "THE NEW MOOD", title: "Keep it simple.\nMake it yours.", body: "A fresh point of view for everyday choices.", cta: "Shop the collection", tone: "olive" },
  ],
} as const;

const tones = {
  rose: { background: "linear-gradient(115deg,#f6e9e4 0%,#f2d8ce 54%,#c77c69 100%)", accent: "#8c3f32", orb: "#b96552" },
  sand: { background: "linear-gradient(115deg,#f3efe4 0%,#ded2bd 56%,#b3a187 100%)", accent: "#554634", orb: "#a48c6b" },
  olive: { background: "linear-gradient(115deg,#e8e9dd 0%,#c7cbb7 56%,#777f62 100%)", accent: "#37422e", orb: "#687653" },
};

export function HomepageHeroSlider({ locale }: { locale: Locale }) {
  const [active, setActive] = useState(0);
  const items = slides[locale];

  useEffect(() => {
    const timer = window.setInterval(() => setActive((current) => (current + 1) % items.length), 6000);
    return () => window.clearInterval(timer);
  }, [items.length]);

  const slide = items[active];
  const tone = tones[slide.tone];

  return (
    <section aria-label={locale === "fa" ? "بنرهای ویژه ودزمانی" : "Vedzmani featured banners"} className="mx-auto w-full max-w-[1440px] px-3 pt-4 sm:px-6 sm:pt-6">
      <div className="relative isolate min-h-[390px] overflow-hidden rounded-2xl sm:min-h-[440px] lg:min-h-[500px]" style={{ background: tone.background }}>
        <div aria-hidden="true" className="absolute inset-y-0 end-0 w-[57%] overflow-hidden">
          <div className="absolute end-[9%] top-[12%] aspect-[4/5] w-[55%] rotate-6 rounded-[48%_48%_12%_12%] border border-white/45 bg-white/20 shadow-2xl backdrop-blur-[2px] sm:end-[15%] sm:w-[42%]" />
          <div className="absolute end-[28%] top-[18%] aspect-[3/4] w-[42%] -rotate-6 rounded-[48%_48%_10%_10%] border border-white/50 bg-black/[0.06] sm:end-[33%] sm:w-[32%]" />
          <div className="absolute -end-12 -top-16 size-52 rounded-full border border-white/35 sm:size-72" />
          <div className="absolute -bottom-20 end-[10%] size-52 rounded-full bg-white/20 blur-2xl sm:size-80" />
          <span className="absolute bottom-[13%] end-[12%] font-serif text-[clamp(5rem,15vw,13rem)] leading-none tracking-[-0.09em] text-white/45" aria-hidden="true">V.</span>
        </div>
        <div className="relative z-10 flex min-h-[390px] max-w-2xl flex-col items-start justify-center px-6 py-12 sm:min-h-[440px] sm:px-12 lg:min-h-[500px] lg:px-16">
          <p className="mb-5 text-xs font-semibold tracking-[0.22em]" style={{ color: tone.accent }}>{slide.eyebrow}</p>
          <h1 className="whitespace-pre-line text-4xl font-semibold leading-[1.18] tracking-tight sm:text-6xl lg:text-7xl" style={{ color: tone.accent }}>{slide.title}</h1>
          <p className="mt-5 max-w-sm text-sm leading-7 sm:text-base" style={{ color: tone.accent }}>{slide.body}</p>
          <Link href={`/${locale}/products`} className="mt-7 inline-flex min-h-12 items-center justify-center rounded-full px-6 text-sm font-semibold transition-transform hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-4" style={{ backgroundColor: tone.accent, color: "#fff" }}>
            {slide.cta}<span aria-hidden="true" className="ms-3">↗</span>
          </Link>
        </div>
        <div className="absolute bottom-5 start-6 z-20 flex items-center gap-2 sm:start-12 lg:start-16" aria-label={locale === "fa" ? "انتخاب اسلاید" : "Choose slide"}>
          {items.map((item, index) => (
            <button key={item.eyebrow} type="button" aria-label={locale === "fa" ? `نمایش بنر ${index + 1}` : `Show banner ${index + 1}`} aria-current={index === active ? "true" : undefined} onClick={() => setActive(index)} className={`h-1.5 rounded-full transition-all ${index === active ? "w-9 bg-neutral-900" : "w-4 bg-neutral-900/30 hover:bg-neutral-900/60"}`} />
          ))}
          <span className="ms-2 text-xs tabular-nums" style={{ color: tone.accent }}>{String(active + 1).padStart(2, "0")} / {String(items.length).padStart(2, "0")}</span>
        </div>
      </div>
    </section>
  );
}
