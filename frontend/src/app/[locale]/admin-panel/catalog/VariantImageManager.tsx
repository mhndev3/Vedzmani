"use client";

import { useCallback, useEffect, useState } from "react";
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
type ImagePage = { results: ImageItem[] };

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

export default function VariantImageManager({ variantId }: { variantId: number }) {
  const [images, setImages] = useState<ImageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [altText, setAltText] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const page = await apiRequest<ImagePage>("GET", `/api/admin/catalog/images/?variant=${variantId}`);
      setImages(page.results);
      setError("");
    } catch (e) {
      setError(message(e));
    } finally {
      setLoading(false);
    }
  }, [variantId]);

  useEffect(() => { void refresh(); }, [refresh]);

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
      setNotice("تصویر اضافه شد و پردازش نسخه‌های بهینه آغاز شد.");
      await refresh();
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
    if (!window.confirm("این تصویر از گالری محصول پنهان شود؟ فایل اصلی برای حفظ سابقه حذف نمی‌شود.")) return;
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
          <p className="mt-1 text-xs text-muted-foreground">تصویر اول، تصویر اصلی کارت محصول است. فرمت‌های JPEG، PNG و WebP تا ۱۲ مگابایت پذیرفته می‌شوند.</p>
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
              <article key={image.id} className="overflow-hidden rounded-xl border border-border">
                <div className="relative aspect-[4/5] bg-muted">
                  <img src={image.url} alt={image.alt_text || "تصویر محصول"} className="h-full w-full object-cover" loading="lazy" />
                  {image.is_primary && <span className="absolute right-2 top-2 rounded-full bg-background/90 px-2 py-1 text-[10px] font-semibold">تصویر اصلی</span>}
                </div>
                <div className="space-y-2 p-2">
                  <p className="text-[11px] text-muted-foreground">{image.width} × {image.height}</p>
                  <div className="flex flex-wrap gap-1">
                    <button type="button" className={buttonClass} disabled={busy || index === 0} onClick={() => void move(index, -1)}>← جابه‌جایی</button>
                    <button type="button" className={buttonClass} disabled={busy || index === images.length - 1} onClick={() => void move(index, 1)}>→</button>
                    <button type="button" className={buttonClass} disabled={busy} onClick={() => void deactivate(image)}>خارج‌کردن</button>
                  </div>
                </div>
              </article>
            ))}
          </div>}
    </section>
  );
}
