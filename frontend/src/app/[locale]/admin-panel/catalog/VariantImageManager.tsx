"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

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
export type StagedVariantImage = { key: string; file: File; alt_text: string };
export type VariantImageDraft = {
  variant: number;
  image_ids: number[];
  deactivate_ids: number[];
  new_images: StagedVariantImage[];
  order: string[];
};

async function getAllImages(variantId: number): Promise<ImageItem[]> {
  const images: ImageItem[] = [];
  let next: string | null = `/api/admin/catalog/images/?variant=${variantId}`;
  const visited = new Set<string>();
  while (next) {
    if (visited.has(next) || visited.size >= 10000) throw new Error("Image pagination did not terminate.");
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
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "مجوز مدیریت تصاویر برای حساب شما فعال نیست.";
  if (error instanceof BrowserApiError && error.status === 413) return "حجم تصویر بیشتر از محدودیت سرور است.";
  return "عملیات تصویر انجام نشد؛ فرمت و حجم فایل را بررسی کنید.";
}

type GalleryEntry = { token: string; existing?: ImageItem; staged?: StagedVariantImage };

export default function VariantImageManager({
  variantId,
  draftMode = true,
  onDraftChange,
  draft,
}: {
  variantId: number;
  draftMode?: boolean;
  onDraftChange?: (draft: VariantImageDraft) => void;
  draft?: VariantImageDraft;
}) {
  const draftRef = useRef<VariantImageDraft | undefined>(draft);
  const [images, setImages] = useState<ImageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [altText, setAltText] = useState("");
  const [deactivateIds, setDeactivateIds] = useState<number[]>(draft?.deactivate_ids ?? []);
  const [stagedImages, setStagedImages] = useState<StagedVariantImage[]>(draft?.new_images ?? []);
  const [order, setOrder] = useState<string[]>(draft?.order ?? []);
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});

  const emitDraft = useCallback((next: {
    deactivate_ids?: number[];
    new_images?: StagedVariantImage[];
    order?: string[];
  }) => {
    const current = draftRef.current;
    const staged = next.new_images ?? stagedImages;
    const removed = next.deactivate_ids ?? deactivateIds;
    const nextOrder = next.order ?? order;
    const value: VariantImageDraft = {
      variant: variantId,
      image_ids: images.map((image) => image.id),
      deactivate_ids: removed,
      new_images: staged,
      order: nextOrder,
    };
    draftRef.current = value;
    onDraftChange?.(value);
  }, [variantId, images, stagedImages, deactivateIds, order, onDraftChange]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const rows = await getAllImages(variantId);
        if (cancelled) return;
        setImages(rows);
        const savedDraft = draftRef.current;
        if (savedDraft?.variant === variantId && savedDraft.order.length) {
          setOrder(savedDraft.order);
        } else {
          const initialOrder = rows.map((image) => `existing:${image.id}`);
          setOrder(initialOrder);
          if (draftMode) {
            const value: VariantImageDraft = {
              variant: variantId, image_ids: rows.map((image) => image.id),
              deactivate_ids: savedDraft?.deactivate_ids ?? [], new_images: savedDraft?.new_images ?? [],
              order: initialOrder,
            };
            draftRef.current = value;
            onDraftChange?.(value);
          }
        }
        setError("");
      } catch (e) {
        if (!cancelled) setError(message(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [variantId, draftMode, onDraftChange]);

  useEffect(() => {
    const next: Record<string, string> = {};
    stagedImages.forEach((item) => { next[item.key] = URL.createObjectURL(item.file); });
    setPreviewUrls(next);
    return () => Object.values(next).forEach((url) => URL.revokeObjectURL(url));
  }, [stagedImages]);

  const entries = useMemo(() => {
    const existing = new Map(images.map((image) => [`existing:${image.id}`, image]));
    const staged = new Map(stagedImages.map((item) => [`new:${item.key}`, item]));
    const tokens = [...order, ...[...existing.keys(), ...staged.keys()].filter((token) => !order.includes(token))];
    return tokens.flatMap((token): GalleryEntry[] => {
      const image = existing.get(token);
      if (image && !deactivateIds.includes(image.id)) return [{ token, existing: image }];
      const pending = staged.get(token);
      return pending ? [{ token, staged: pending }] : [];
    });
  }, [images, stagedImages, order, deactivateIds]);

  function updateOrder(next: string[]) {
    setOrder(next);
    emitDraft({ order: next });
  }

  function addFiles(files: FileList | null) {
    if (!files?.length) return;
    const selected = Array.from(files);
    if (stagedImages.length + selected.length > 20) {
      setError("حداکثر ۲۰ تصویر جدید را می‌توان هم‌زمان برای یک رنگ ذخیره کرد.");
      return;
    }
    const additions = selected.map((file) => ({
      key: crypto.randomUUID().replace(/-/g, ""),
      file,
      alt_text: altText.trim().slice(0, 200),
    }));
    const nextStaged = [...stagedImages, ...additions];
    const nextOrder = [...order, ...additions.map((item) => `new:${item.key}`)];
    setStagedImages(nextStaged);
    setOrder(nextOrder);
    setAltText("");
    setError("");
    emitDraft({ new_images: nextStaged, order: nextOrder });
    setNotice("تصویر فقط در پیش‌نویس مرورگر قرار گرفت؛ هنوز به محصول یا فضای ذخیره‌سازی سرور ارسال نشده است.");
  }

  function removeStaged(item: StagedVariantImage) {
    const nextStaged = stagedImages.filter((row) => row.key !== item.key);
    const nextOrder = order.filter((token) => token !== `new:${item.key}`);
    setStagedImages(nextStaged);
    setOrder(nextOrder);
    emitDraft({ new_images: nextStaged, order: nextOrder });
    setNotice("تصویر جدید از پیش‌نویس حذف شد و هیچ فایلی به سرور ارسال نشد.");
  }

  function toggleDeactivate(image: ImageItem) {
    if (deactivateIds.includes(image.id)) {
      const nextRemoved = deactivateIds.filter((id) => id !== image.id);
      const nextOrder = [...order, `existing:${image.id}`];
      setDeactivateIds(nextRemoved);
      setOrder(nextOrder);
      emitDraft({ deactivate_ids: nextRemoved, order: nextOrder });
      setNotice("تصویر به پیش‌نویس گالری بازگردانده شد.");
      return;
    }
    if (!window.confirm("این تصویر پس از ذخیره از گالری پنهان شود؟ فایل اصلی برای حفظ سابقه حذف نمی‌شود.")) return;
    const nextRemoved = [...deactivateIds, image.id];
    const nextOrder = order.filter((token) => token !== `existing:${image.id}`);
    setDeactivateIds(nextRemoved);
    setOrder(nextOrder);
    emitDraft({ deactivate_ids: nextRemoved, order: nextOrder });
    setNotice("خارج‌کردن تصویر پیش‌نویس شد؛ با ذخیره همه تغییرات اعمال می‌شود.");
  }

  async function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= entries.length) return;
    const next = [...entries];
    [next[index], next[target]] = [next[target], next[index]];
    updateOrder(next.map((entry) => entry.token));
    setNotice("ترتیب جدید پیش‌نویس شد؛ تصویر اول پس از ذخیره، تصویر اصلی خواهد بود.");
  }

  const removedImages = images.filter((image) => deactivateIds.includes(image.id));

  return (
    <section className="mt-5 border-t border-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="font-semibold">تصاویر این رنگ</h4>
          <p className="mt-1 text-xs text-muted-foreground">تصویر اول، تصویر اصلی کارت محصول است. JPEG، PNG و WebP تا ۸ مگابایت پذیرفته می‌شوند.</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs">متن جایگزین تصویر
            <input value={altText} onChange={(event) => setAltText(event.target.value)} maxLength={200} className="mt-1 block w-52 rounded-lg border border-border bg-background px-2 py-2 text-xs" placeholder="مثلاً نمای روبه‌روی بافت" />
          </label>
          <label className={buttonClass + " cursor-pointer"}>
            ＋ افزودن تصویر
            <input type="file" multiple accept="image/jpeg,image/png,image/webp" className="sr-only" disabled={busy || loading} onChange={(event) => { addFiles(event.currentTarget.files); event.currentTarget.value = ""; }} />
          </label>
        </div>
      </div>
      {error && <p role="alert" className="mt-3 rounded-lg bg-destructive/10 p-2 text-xs text-destructive">{error}</p>}
      {notice && <p role="status" className="mt-3 rounded-lg bg-muted p-2 text-xs">{notice}</p>}
      {loading ? <p className="py-4 text-xs text-muted-foreground">در حال دریافت تصاویر…</p> : entries.length === 0 && removedImages.length === 0 ? <p className="py-4 text-xs text-muted-foreground">برای این رنگ هنوز تصویری ثبت نشده است.</p> : (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {entries.map((entry, index) => {
              const image = entry.existing;
              const staged = entry.staged;
              return (
                <article key={entry.token} className="overflow-hidden rounded-xl border border-border">
                  <div className="relative aspect-[4/5] bg-muted">
                    {image ? <Image src={image.url} alt={image.alt_text || "تصویر محصول"} fill sizes="(max-width: 640px) 50vw, 25vw" className="object-cover" unoptimized /> :
                      staged ? <img src={previewUrls[staged.key]} alt={staged.alt_text || "پیش‌نمایش تصویر جدید"} className="h-full w-full object-cover" /> : null}
                    {index === 0 && <span className="absolute right-2 top-2 rounded-full bg-background/90 px-2 py-1 text-[10px] font-semibold">تصویر اصلی پس از ذخیره</span>}
                    {staged && <span className="absolute bottom-2 right-2 rounded-full bg-primary px-2 py-1 text-[10px] font-semibold text-primary-foreground">پیش‌نویس · ذخیره‌نشده</span>}
                  </div>
                  <div className="space-y-2 p-2">
                    <p className="truncate text-[11px] text-muted-foreground">{image ? `${image.width} × ${image.height}` : staged?.file.name}</p>
                    <div className="flex flex-wrap gap-1">
                      <button type="button" className={buttonClass} disabled={busy || index === 0} onClick={() => void move(index, -1)}>← جابه‌جایی</button>
                      <button type="button" className={buttonClass} disabled={busy || index === entries.length - 1} onClick={() => void move(index, 1)}>→</button>
                      {image ? <button type="button" className={buttonClass} disabled={busy} onClick={() => toggleDeactivate(image)}>خارج‌کردن</button> :
                        staged ? <button type="button" className={buttonClass} disabled={busy} onClick={() => removeStaged(staged)}>حذف پیش‌نویس</button> : null}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
          {removedImages.length > 0 && <div className="mt-4 rounded-lg border border-dashed border-border p-3">
            <p className="mb-2 text-xs font-semibold">تصاویر علامت‌خورده برای خارج‌کردن</p>
            <div className="flex flex-wrap gap-2">
              {removedImages.map((image) => <button key={image.id} type="button" className={buttonClass} onClick={() => toggleDeactivate(image)}>بازگردانی تصویر #{image.id}</button>)}
            </div>
          </div>}
        </>
      )}
    </section>
  );
}
