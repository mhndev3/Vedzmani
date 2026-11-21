"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/auth/api";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Props = {
  productId: number;
  name: string;
  description: string;
  price: string;
  salePrice: string | null;
};

function validToman(value: string): boolean {
  return /^\\d{1,14}$/.test(value.trim()) && Number(value) > 0;
}

export function StorefrontProductEditor(props: Props) {
  const router = useRouter();
  const [canSeeEditor, setCanSeeEditor] = useState(false);
  const [checking, setChecking] = useState(true);
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState(false);
  const [name, setName] = useState(props.name);
  const [description, setDescription] = useState(props.description);
  const [price, setPrice] = useState(props.price);
  const [salePrice, setSalePrice] = useState(props.salePrice ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;
    authApi.me().then((user) => {
      if (active) setCanSeeEditor(Boolean(user?.is_staff));
    }).catch(() => {
      if (active) setCanSeeEditor(false);
    }).finally(() => {
      if (active) setChecking(false);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!open) {
      setName(props.name);
      setDescription(props.description);
      setPrice(props.price);
      setSalePrice(props.salePrice ?? "");
      setPreview(false);
      setError("");
      setSaved(false);
    }
  }, [open, props.name, props.description, props.price, props.salePrice]);

  if (checking || !canSeeEditor) return null;

  function validate(): string | null {
    if (!name.trim()) return "عنوان محصول الزامی است.";
    if (name.trim().length > 200) return "عنوان محصول نباید بیشتر از ۲۰۰ نویسه باشد.";
    if (!validToman(price)) return "قیمت باید عدد صحیح و مثبت به تومان باشد.";
    if (salePrice.trim() && (!validToman(salePrice) || Number(salePrice) >= Number(price))) {
      return "قیمت فروش باید عددی مثبت و کمتر از قیمت اصلی باشد.";
    }
    return null;
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      setPreview(false);
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiRequest("PATCH", `/api/admin/catalog/products/${props.productId}/`, {
        name: name.trim(),
        description,
        price: price.trim(),
        sale_price: salePrice.trim() ? salePrice.trim() : null,
      });
      setSaved(true);
      setOpen(false);
      router.refresh();
    } catch (cause) {
      if (cause instanceof BrowserApiError && cause.status === 403) {
        setError("حساب شما مجوز ویرایش محصول را ندارد.");
      } else {
        setError("ذخیره تغییرات انجام نشد. اطلاعات را بررسی کنید و دوباره تلاش کنید.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-lg border border-primary/40 px-3 py-2 text-xs font-semibold text-primary transition hover:bg-primary/5"
        aria-label="ویرایش این محصول"
      >
        <span aria-hidden="true">✎</span>
        ویرایش همین محصول
      </button>

      {open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto bg-black/50 p-4" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !saving) setOpen(false);
        }}>
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="storefront-product-editor-title"
            dir="rtl"
            className="my-auto w-full max-w-xl rounded-2xl border border-border bg-card p-5 shadow-2xl sm:p-6"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 id="storefront-product-editor-title" className="text-lg font-bold">ویرایش محصول در فروشگاه</h2>
                <p className="mt-1 text-xs leading-6 text-muted-foreground">تغییرات پس از ذخیره مستقیماً روی اطلاعات محصول اعمال می‌شوند.</p>
              </div>
              <button type="button" onClick={() => setOpen(false)} disabled={saving} className="rounded-lg px-3 py-1 text-xl text-muted-foreground hover:bg-muted" aria-label="بستن">×</button>
            </div>

            <form className="mt-5 space-y-4" onSubmit={save}>
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">عنوان محصول</span>
                <input value={name} onChange={(event) => setName(event.target.value)} maxLength={200} required className="min-h-11 w-full rounded-xl border border-border bg-background px-3 text-sm outline-none focus:border-primary" />
              </label>
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">توضیحات</span>
                <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={5} className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm leading-7 outline-none focus:border-primary" />
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block space-y-1.5">
                  <span className="text-sm font-medium">قیمت اصلی (تومان)</span>
                  <input inputMode="numeric" value={price} onChange={(event) => setPrice(event.target.value)} required className="min-h-11 w-full rounded-xl border border-border bg-background px-3 text-sm outline-none focus:border-primary" />
                </label>
                <label className="block space-y-1.5">
                  <span className="text-sm font-medium">قیمت فروش (تومان)</span>
                  <input inputMode="numeric" value={salePrice} onChange={(event) => setSalePrice(event.target.value)} placeholder="بدون تخفیف خالی بماند" className="min-h-11 w-full rounded-xl border border-border bg-background px-3 text-sm outline-none focus:border-primary" />
                </label>
              </div>

              {preview && (
                <div className="rounded-xl border border-dashed border-primary/50 bg-primary/5 p-4" aria-live="polite">
                  <p className="mb-2 text-xs font-semibold text-primary">پیش‌نمایش اطلاعات جدید</p>
                  <h3 className="font-bold">{name.trim() || "عنوان محصول"}</h3>
                  <p className="mt-2 whitespace-pre-line text-sm leading-7 text-muted-foreground">{description || "بدون توضیحات"}</p>
                  <p className="mt-3 text-sm font-semibold">{Number(price || 0).toLocaleString("fa-IR")} تومان</p>
                  {salePrice.trim() && <p className="text-sm text-primary">{Number(salePrice || 0).toLocaleString("fa-IR")} تومان با تخفیف</p>}
                </div>
              )}

              {error && <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
              {saved && <p role="status" className="text-sm text-primary">تغییرات ذخیره شد.</p>}
              <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-4">
                <button type="button" onClick={() => setOpen(false)} disabled={saving} className="min-h-10 rounded-xl border border-border px-4 text-sm font-medium hover:bg-muted">انصراف</button>
                <button type="button" onClick={() => {
                  const validationError = validate();
                  setError(validationError ?? "");
                  setPreview(!validationError);
                }} disabled={saving} className="min-h-10 rounded-xl border border-primary/40 px-4 text-sm font-semibold text-primary hover:bg-primary/5">پیش‌نمایش</button>
                <button type="submit" disabled={saving} className="min-h-10 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{saving ? "در حال ذخیره…" : "ذخیره در فروشگاه"}</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
