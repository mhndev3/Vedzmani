"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Locale } from "@/i18n/config";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Favorite = { product_id: number; product_slug: string; product_name: string };

function productPageUrl(locale: Locale, productSlug: string) {
  const url = new URL(`/${locale}/products/${encodeURIComponent(productSlug)}`, window.location.origin);
  const color = new URL(window.location.href).searchParams.get("color");
  if (color) url.searchParams.set("color", color);
  return url.toString();
}

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
  const [copied, setCopied] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const shareDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    let active = true;
    apiRequest<Favorite[]>("GET", "/api/catalog/favorites/")
      .then((items) => { if (active) setSaved(items.some((item) => item.product_id === productId)); })
      .catch(() => { /* Guests can share; the save action will request sign-in. */ });
    return () => { active = false; };
  }, [productId]);

  useEffect(() => {
    const dialog = shareDialog.current;
    if (!dialog) return;
    if (shareOpen && !dialog.open) dialog.showModal();
    if (!shareOpen && dialog.open) dialog.close();
  }, [shareOpen]);

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
    const url = productPageUrl(locale, productSlug);
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
      } else {
        const input = document.createElement("textarea");
        input.value = url;
        input.setAttribute("readonly", "");
        input.style.position = "fixed";
        input.style.opacity = "0";
        document.body.appendChild(input);
        input.select();
        const copiedToClipboard = document.execCommand("copy");
        input.remove();
        if (!copiedToClipboard) throw new Error("Clipboard copy failed");
      }
      setCopied(true);
      setMessage("لینک محصول کپی شد.");
    } catch {
      setCopied(false);
      setMessage("کپی خودکار ممکن نشد؛ آدرس صفحه را از نوار مرورگر کپی کنید.");
    }
  }

  async function nativeShare() {
    const url = productPageUrl(locale, productSlug);
    if (!navigator.share) return copyLink();
    try {
      await navigator.share({ title: productName, text: productName, url });
    } catch {
      /* Cancelling the device share sheet is not an error. */
    }
  }

  const links = shareLinks(shareUrl, productName);
  const signInTarget = `/${locale}/sign-in?next=${encodeURIComponent(`/${locale}/products/${productSlug}`)}`;

  return (
    <div className="mt-5 flex flex-wrap items-center gap-2">
      <button type="button" onClick={toggleFavorite} disabled={busy} aria-pressed={saved}
        className="inline-flex h-10 items-center gap-2 rounded-full border border-border bg-card px-4 text-sm font-medium shadow-sm transition hover:-translate-y-0.5 hover:bg-muted disabled:opacity-60">
        <span aria-hidden="true">{saved ? "♥" : "♡"}</span>{saved ? "نشان‌شده" : "نشان کردن"}
      </button>
      <button type="button" onClick={() => { setCopied(false); setShareUrl(productPageUrl(locale, productSlug)); setShareOpen(true); }} aria-expanded={shareOpen}
        aria-haspopup="dialog"
        className="inline-flex h-10 items-center gap-2 rounded-full border border-border bg-card px-4 text-sm font-medium shadow-sm transition hover:-translate-y-0.5 hover:bg-muted">
        <span aria-hidden="true">↗</span> اشتراک‌گذاری
      </button>

      <dialog
        ref={shareDialog}
        aria-labelledby="product-share-title"
        onClose={() => setShareOpen(false)}
        onCancel={() => setShareOpen(false)}
        onClick={(event) => { if (event.target === event.currentTarget) setShareOpen(false); }}
        className="fixed inset-0 m-auto max-h-[min(85vh,36rem)] w-[calc(100%-2rem)] max-w-md overflow-y-auto rounded-3xl border border-border bg-card p-0 text-foreground shadow-2xl backdrop:bg-black/50"
      >
        <div className="p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <h2 id="product-share-title" className="text-base font-semibold">اشتراک‌گذاری محصول</h2>
              <p className="mt-1 truncate text-xs text-muted-foreground">{productName}</p>
            </div>
            <button type="button" onClick={() => setShareOpen(false)} aria-label="بستن پنجره اشتراک‌گذاری"
              className="inline-flex size-9 shrink-0 items-center justify-center rounded-full border border-border text-muted-foreground transition hover:bg-muted hover:text-foreground">
              <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none">
                <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          <button type="button" onClick={() => void copyLink()}
            className="mt-5 flex min-h-14 w-full items-center justify-between gap-3 rounded-2xl border border-border bg-muted/50 px-4 py-3 text-sm font-semibold transition hover:border-primary/40 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
            <span>{copied ? "لینک محصول کپی شد" : "کپی لینک محصول"}</span>
            <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5 shrink-0" fill="none">
              <rect x="8" y="8" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.7" />
              <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </button>

          <div className="mt-3 grid grid-cols-2 gap-2">
            <button type="button" onClick={() => void nativeShare()}
              className="rounded-xl border border-border px-3 py-2.5 text-sm transition hover:bg-muted">اشتراک‌گذاری دستگاه</button>
            <a href={links.telegram} target="_blank" rel="noopener noreferrer"
              className="rounded-xl border border-border px-3 py-2.5 text-center text-sm transition hover:bg-muted">تلگرام</a>
            <a href={links.whatsapp} target="_blank" rel="noopener noreferrer"
              className="rounded-xl border border-border px-3 py-2.5 text-center text-sm transition hover:bg-muted">واتساپ</a>
            <a href={links.eitaa} target="_blank" rel="noopener noreferrer"
              className="rounded-xl border border-border px-3 py-2.5 text-center text-sm transition hover:bg-muted">ایتا</a>
            <button type="button" onClick={() => void nativeShare()}
              className="rounded-xl border border-border px-3 py-2.5 text-sm transition hover:bg-muted">بله</button>
            <button type="button" onClick={() => void nativeShare()}
              className="rounded-xl border border-border px-3 py-2.5 text-sm transition hover:bg-muted">روبیکا</button>
          </div>
          {message && <p role="status" className="mt-4 text-xs text-muted-foreground">{message}</p>}
        </div>
      </dialog>

      {message && !shareOpen && (
        <p role="status" className="basis-full text-xs text-muted-foreground">
          {message} {needsSignIn && <Link className="font-semibold underline underline-offset-4" href={signInTarget}>ورود به حساب کاربری</Link>}
        </p>
      )}
    </div>
  );
}
