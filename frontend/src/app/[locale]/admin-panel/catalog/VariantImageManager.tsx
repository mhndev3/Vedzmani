"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { apiRequest, apiUploadRequest, BrowserApiError } from "@/lib/browser-api";

type ImageItem = {
  id: number;
  variant: number;
  url: string;
  alt_text: string;
  position: number;
  is_primary: boolean;
  width: number;
  height: number;
  content_type: string;
  file_size: number | null;
  is_active: boolean;
};
type ImagePage = { results: ImageItem[]; next: string | null };

async function getAllImages(variantId: number): Promise<ImageItem[]> {
  const images: ImageItem[] = [];
  let next: string | null = `/api/admin/catalog/images/?variant=${variantId}`;
  const visited = new Set<string>();
  while (next) {
    if (visited.has(next) || visited.size >= 10000) {
      throw new Error("Image pagination did not terminate.");
    }
    visited.add(next);
    const page: ImagePage = await apiRequest<ImagePage>("GET", next);
    images.push(...page.results);
    next = page.next
      ? new URL(page.next, window.location.origin).pathname + new URL(page.next, window.location.origin).search
      : null;
  }
  return images;
}

const buttonClass = "rounded-lg border border-border px-3 py-2 text-xs hover:bg-muted disabled:opacity-50";

function message(error: unknown): string {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) {
    return "مجوز مدیریت تصاویر برای حساب شما فعال نیست.";
  }
  if (error instanceof BrowserApiError && error.status === 413) {
    return "حجم تصویر بیشتر از محدودیت سرور است.";
  }
  return "عملیات تصویر انجام نشد؛ فرمت و حجم فایل را بررسی کنید.";
}

type ImageDraft = { variant: number; image_ids: number[]; deactivate_ids: number[] };

export default function VariantImageManager({
  variantId,
  draftMode = false,
  onDraftChange,
  draft,
}: {
  variantId: number;
  draftMode?: boolean;
  onDraftChange?: (draft: ImageDraft) => void;
  draft?: ImageDraft;
}) {
  const draftRef = useRef(draft);
  const [images, setImages] = useState<ImageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [altText, setAltText] = useState("");
  const [deactivateIds, setDeactivateIds] = useState<number[]>(draft?.deactivate_ids ?? []);

  const applyDraftOrder = useCallback((rows: ImageItem[]) => {
    const current = draftRef.current;
    if (!current || current.variant !== variantId) return rows;
    const positions = new Map<number, number>();
    current.image_ids.forEach((id, index) => positions.set(id, index));
    return [...rows].sort((a, b) => (positions.get(a.id) ?? Number.MAX_SAFE_INTEGER) - (positions.get(b.id) ?? Number.MAX_SAFE_INTEGER));
  }, [variantId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const rows = await getAllImages(variantId);
        if (!cancelled) {
          setImages(applyDraftOrder(rows));
          setError("");
        }
      } catch (e) {
        if (!cancelled) setError(message(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [applyDraftOrder, variantId]);

  async function upload(file?: File) {
    if (!file) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const body = new FormData();
      body.append("variant", String(variantId));
      body.append("file", file);
      body.append("alt_text", altText);
      await apiUploadRequest<ImageItem>("/api/admin/catalog/images/upload/", body);
      setAltText("");
      const rows = await getAllImages(variantId);
      const orderedRows = applyDraftOrder(rows);
      setImages(orderedRows);
      if (draftMode) {
        const nextDraft = {
          variant: variantId,
          image_ids: orderedRows.map((image) => image.id),
          deactivate_ids: deactivateIds,
        };
        draftRef.current = nextDraft;
        onDraftChange?.(nextDraft);
      }
      setNotice("تصویر آپلود شد. ترتیب و خارج‌کردن تصاویر با دکمه ذخیره همه تغییرات اعمال می‌شود.");
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  async function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= images.length) return;
    const reordered = [...images];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    if (draftMode) {
      setImages(reordered);
      const nextDraft = {
        variant: variantId,
        image_ids: reordered.map((image) => image.id),
        deactivate_ids: deactivateIds,
      };
      draftRef.current = nextDraft;
      onDraftChange?.(nextDraft);
      setNotice("ترتیب جدید پیش‌نویس شد؛ با ذخیره همه تغییرات اعمال می‌شود.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      const saved = await apiRequest<ImageItem[]>("POST", "/api/admin/catalog/images/reorder/", {
        variant: variantId,
        image_ids: reordered.map((image) => image.id),
      });
      setImages(saved);
      setNotice("ترتیب تصاویر ذخیره شد؛ تصویر اول، تصویر اصلی است.");
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  async function deactivate(image: ImageItem) {
    if (deactivateIds.includes(image.id)) {
      const next = deactivateIds.filter((id) => id !== image.id);
      setDeactivateIds(next);
      const nextDraft = { variant: variantId, image_ids: images.map((item) => item.id), deactivate_ids: next };
      draftRef.current = nextDraft;
      onDraftChange?.(nextDraft);
      setNotice("تصویر به پیش‌نویس گالری بازگردانده شد.");
      return;
    }
    if (!window.confirm("این تصویر پس از ذخیره از گالری پنهان شود؟ فایل اصلی برای حفظ سابقه حذف نمی‌شود.")) return;
    if (draftMode) {
      const next = [...deactivateIds, image.id];
      setDeactivateIds(next);
      const nextDraft = { variant: variantId, image_ids: images.map((item) => item.id), deactivate_ids: next };
      draftRef.current = nextDraft;
      onDraftChange?.(nextDraft);
      setNotice("حذف تصویر پیش‌نویس شد؛ با ذخیره همه تغییرات اعمال می‌شود.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest<ImageItem>("PATCH", `/api/admin/catalog/images/${image.id}/deactivate/`, {});
      setNotice("تصویر از گالری خارج شد.");
      await refresh();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-5 border-t border-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="font-semibold">تصاویر این رنگ</h4>
          <p className="mt-1 text-xs text-muted-foreground">تصویر اول، تصویر اصلی کارت محصول است. فرمت‌های JPEG، PNG و WebP تا ۸ مگابایت پذیرفته می‌شوند.</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs">متن جایگزین تصویر
            <input value={altText} onChange={(event) => setAltText(event.target.value)} maxLength={200} className="mt-1 block w-52 rounded-lg border border-border bg-background px-2 py-2 text-xs" placeholder="مثلاً نمای روبه‌روی بافت" />
          </label>
          <label className={buttonClass + " cursor-pointer"}>
          {busy ? "در حال انجام…" : "＋ افزودن تصویر"}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            disabled={busy}
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              event.currentTarget.value = "";
              void upload(file);
            }}
          />
          </label>
        </div>
      </div>
      {error && <p role="alert" className="mt-3 rounded-lg bg-destructive/10 p-2 text-xs text-destructive">{error}</p>}
      {notice && <p role="status" className="mt-3 rounded-lg bg-muted p-2 text-xs">{notice}</p>}
      {loading ? <p className="py-4 text-xs text-muted-foreground">در حال دریافت تصاویر…</p> :
        images.length === 0 ? <p className="py-4 text-xs text-muted-foreground">برای این رنگ هنوز تصویری ثبت نشده است.</p> :
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {images.map((image, index) => (
              <article key={image.id} className={"overflow-hidden rounded-xl border border-border " + (deactivateIds.includes(image.id) ? "opacity-60" : "")}>
                <div className="relative aspect-[4/5] bg-muted">
                  <Image src={image.url} alt={image.alt_text || "تصویر محصول"} fill sizes="(max-width: 640px) 50vw, 25vw" className="object-cover" unoptimized />
                  {image.is_primary && <span className="absolute right-2 top-2 rounded-full bg-background/90 px-2 py-1 text-[10px] font-semibold">تصویر اصلی</span>}
                  {deactivateIds.includes(image.id) && <span className="absolute bottom-2 right-2 rounded-full bg-destructive px-2 py-1 text-[10px] font-semibold text-white">پس از ذخیره حذف می‌شود</span>}
                </div>
                <div className="space-y-2 p-2">
                  <p className="text-[11px] text-muted-foreground">{image.width} × {image.height}</p>
                  <div className="flex flex-wrap gap-1">
                    <button type="button" className={buttonClass} disabled={busy || index === 0} onClick={() => void move(index, -1)}>← جابه‌جایی</button>
                    <button type="button" className={buttonClass} disabled={busy || index === images.length - 1} onClick={() => void move(index, 1)}>→</button>
                    <button type="button" className={buttonClass} disabled={busy} onClick={() => void deactivate(image)}>{deactivateIds.includes(image.id) ? "بازگردانی" : draftMode ? "حذف با ذخیره" : "خارج‌کردن"}</button>
                  </div>
                </div>
              </article>
            ))}
          </div>}
    </section>
  );
}
