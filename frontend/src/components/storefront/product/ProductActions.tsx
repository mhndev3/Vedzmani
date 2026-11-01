"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Locale } from "@/i18n/config";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Favorite = { product_id: number; product_slug: string; product_name: string };

function shareLinks(url: string, title: string) {
  const encodedUrl = encodeURIComponent(url);
  const encodedTitle = encodeURIComponent(title);
  return {
    telegram: `https://t.me/share/url?url=${encodedUrl}&text=${encodedTitle}`,
    whatsapp: `https://api.whatsapp.com/send?text=${encodedTitle}%20${encodedUrl}`,
    eitaa: `https://eitaa.com/share/url?url=${encodedUrl}&text=${encodedTitle}`,
  };
}

export function ProductActions({ productId, productSlug, productName, locale }: {
  productId: number;
  productSlug: string;
  productName: string;
  locale: Locale;
}) {
  const [saved, setSaved] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [needsSignIn, setNeedsSignIn] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    apiRequest<Favorite[]>("GET", "/api/catalog/favorites/")
      .then((items) => { if (active) setSaved(items.some((item) => item.product_id === productId)); })
      .catch(() => { /* Guests can share; the save action will request sign-in. */ });
    return () => { active = false; };
  }, [productId]);

  async function toggleFavorite() {
    if (busy) return;
    setBusy(true);
    setNeedsSignIn(false);
    setMessage("");
    try {
      if (saved) {
        await apiRequest("DELETE", `/api/catalog/favorites/${encodeURIComponent(productSlug)}/`);
        setSaved(false);
        setMessage("از نشان‌شده‌ها حذف شد.");
      } else {
        await apiRequest("POST", "/api/catalog/favorites/", { product_id: productId });
        setSaved(true);
        setMessage("به نشان‌شده‌ها اضافه شد.");
      }
    } catch (error) {
      const anonymous = error instanceof BrowserApiError && error.status === 401;
      setNeedsSignIn(anonymous);
      setMessage(anonymous ? "برای نشان‌کردن محصول ابتدا وارد حساب کاربری شوید." : "ذخیره محصول انجام نشد. دوباره تلاش کنید.");
    } finally {
      setBusy(false);
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setMessage("لینک محصول کپی شد.");
    } catch {
      setMessage("کپی خودکار ممکن نشد؛ آدرس صفحه را از نوار مرورگر کپی کنید.");
    }
  }

  async function nativeShare() {
    if (!navigator.share) return copyLink();
    try { await navigator.share({ title: productName, url: window.location.href }); }
    catch { /* A cancelled native share is not an error. */ }
  }

  const links = shareLinks(typeof window === "undefined" ? "" : window.location.href, productName);
  const signInTarget = `/${locale}/sign-in?next=${encodeURIComponent(`/${locale}/products/${productSlug}`)}`;

  return (
    <div className="mt-5 flex flex-wrap items-center gap-2">
      <button type="button" onClick={toggleFavorite} disabled={busy} aria-pressed={saved}
        className="inline-flex h-10 items-center gap-2 rounded-full border border-border bg-card px-4 text-sm font-medium shadow-sm transition hover:-translate-y-0.5 hover:bg-muted disabled:opacity-60">
        <span aria-hidden="true">{saved ? "♥" : "♡"}</span>{saved ? "نشان‌شده" : "نشان کردن"}
      </button>
      <button type="button" onClick={() => setShareOpen((open) => !open)} aria-expanded={shareOpen}
        className="inline-flex h-10 items-center gap-2 rounded-full border border-border bg-card px-4 text-sm font-medium shadow-sm transition hover:-translate-y-0.5 hover:bg-muted">
        <span aria-hidden="true">↗</span> اشتراک‌گذاری
      </button>
      {shareOpen && (
        <div className="basis-full rounded-2xl border border-border bg-card p-4 shadow-lg" role="group" aria-label="گزینه‌های اشتراک‌گذاری">
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={copyLink} className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted">کپی لینک</button>
            <button type="button" onClick={nativeShare} className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted">اشتراک‌گذاری دستگاه</button>
            <a href={links.telegram} target="_blank" rel="noopener noreferrer" className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted">تلگرام</a>
            <a href={links.whatsapp} target="_blank" rel="noopener noreferrer" className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted">واتساپ</a>
            <a href={links.eitaa} target="_blank" rel="noopener noreferrer" className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted">ایتا</a>
            <button type="button" onClick={copyLink} className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted">کپی برای بله</button>
            <button type="button" onClick={copyLink} className="rounded-full border border-border px-3 py-2 text-sm hover:bg-muted">کپی برای روبیکا</button>
          </div>
        </div>
      )}
      {message && <p role="status" className="basis-full text-xs text-muted-foreground">{message} {needsSignIn && <Link className="font-semibold underline underline-offset-4" href={signInTarget}>ورود به حساب کاربری</Link>}</p>}
    </div>
  );
}
