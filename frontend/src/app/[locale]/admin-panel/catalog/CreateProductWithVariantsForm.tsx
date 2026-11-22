"use client";

import { useState, type FormEvent } from "react";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Category = { id: number; name: string; is_active: boolean };
type Collection = { id: number; name: string; is_active: boolean };
type Size = { id: number; code: string; label: string; position: number };
type Product = {
  id: number; product_code: string | null; name: string; slug: string; description: string;
  price: string; sale_price: string | null; category: number; collections: number[]; is_active: boolean;
};
type ColorDraft = {
  key: number; name: string; slug: string; hex_color: string;
  sizes: { size: number; sku: string }[];
};

const field = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary";
const primary = "rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondary = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";

function errorMessage(error: unknown) {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) {
    return "برای ساخت محصول، رنگ و سایز مجوز کافی ندارید.";
  }
  if (error instanceof BrowserApiError && error.status === 400) {
    return "اطلاعات محصول معتبر نیست یا نامک و SKU تکراری است. موارد مشخص‌شده را بررسی کنید.";
  }
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "ساخت محصول انجام نشد. اطلاعات را بررسی کنید و دوباره تلاش کنید.";
}

export default function CreateProductWithVariantsForm({
  categories,
  collections,
  sizes,
  onCancel,
  onCreated,
}: {
  categories: Category[];
  collections: Collection[];
  sizes: Size[];
  onCancel: () => void;
  onCreated: (product: Product) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [salePrice, setSalePrice] = useState("");
  const [categoryId, setCategoryId] = useState(String(categories.find(item => item.is_active)?.id ?? ""));
  const [collectionIds, setCollectionIds] = useState<number[]>([]);
  const [colors, setColors] = useState<ColorDraft[]>([
    { key: 1, name: "", slug: "", hex_color: "#000000", sizes: [] },
  ]);
  const [nextKey, setNextKey] = useState(2);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function updateColor(index: number, patch: Partial<ColorDraft>) {
    setColors(current => current.map((color, i) => i === index ? { ...color, ...patch } : color));
  }

  function toggleSize(index: number, sizeId: number, checked: boolean) {
    setColors(current => current.map((color, i) => {
      if (i !== index) return color;
      return {
        ...color,
        sizes: checked
          ? [...color.sizes, { size: sizeId, sku: "" }]
          : color.sizes.filter(item => item.size !== sizeId),
      };
    }));
  }

  function updateSku(colorIndex: number, sizeId: number, sku: string) {
    setColors(current => current.map((color, i) => i === colorIndex
      ? { ...color, sizes: color.sizes.map(item => item.size === sizeId ? { ...item, sku } : item) }
      : color));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!categoryId) {
      setError("دسته‌بندی محصول را انتخاب کنید.");
      return;
    }
    if (colors.length === 0 || colors.some(color => !color.name.trim() || !color.slug.trim() || color.sizes.length === 0)) {
      setError("برای هر رنگ، نام و شناسه انگلیسی و دست‌کم یک سایز انتخاب کنید.");
      return;
    }
    if (colors.some(color => color.sizes.some(item => !item.sku.trim()))) {
      setError("برای تمام ترکیب‌های رنگ و سایز، SKU جداگانه وارد کنید.");
      return;
    }

    setSaving(true);
    try {
      const product = await apiRequest<Product>("POST", "/api/admin/catalog/products/create-with-variants/", {
        name: name.trim(),
        slug: slug.trim(),
        description,
        price,
        sale_price: salePrice || null,
        category: Number(categoryId),
        collections: collectionIds,
        colors: colors.map(color => ({
          name: color.name.trim(),
          slug: color.slug.trim(),
          hex_color: color.hex_color,
          sizes: color.sizes.map(item => ({ size: item.size, sku: item.sku.trim() })),
        })),
      });
      await onCreated(product);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="mb-7 rounded-2xl border border-border bg-card p-5 sm:p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">ساخت محصول با رنگ‌ها و سایزها</h2>
          <p className="mt-1 text-xs leading-6 text-muted-foreground">محصول، رنگ‌ها و SKU سایزها در یک تراکنش ساخته می‌شوند. موجودی اولیه همه ترکیب‌ها صفر می‌ماند.</p>
        </div>
        <button type="button" className={secondary} onClick={onCancel}>انصراف</button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-sm">نام محصول<input required maxLength={200} value={name} onChange={event => setName(event.target.value)} className={field} /></label>
        <label className="text-sm">شناسه انگلیسی (Slug)<input required maxLength={220} value={slug} onChange={event => setSlug(event.target.value)} dir="ltr" className={field} /></label>
        <label className="text-sm">دسته‌بندی<select required value={categoryId} onChange={event => setCategoryId(event.target.value)} className={field}><option value="">انتخاب دسته‌بندی</option>{categories.filter(item => item.is_active).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="text-sm">قیمت اصلی (تومان)<input required type="number" min="1" step="1" value={price} onChange={event => setPrice(event.target.value)} className={field} dir="ltr" /></label>
        <label className="text-sm">قیمت با تخفیف (اختیاری)<input type="number" min="1" step="1" value={salePrice} onChange={event => setSalePrice(event.target.value)} className={field} dir="ltr" /></label>
        <label className="text-sm sm:col-span-2 lg:col-span-1">توضیحات<textarea value={description} onChange={event => setDescription(event.target.value)} rows={2} className={field} /></label>
      </div>

      <div className="mt-4">
        <p className="mb-2 text-sm font-medium">مجموعه‌ها</p>
        <div className="flex flex-wrap gap-2">
          {collections.filter(item => item.is_active).map(item => (
            <label key={item.id} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm">
              <input type="checkbox" checked={collectionIds.includes(item.id)} onChange={event => setCollectionIds(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} />
              {item.name}
            </label>
          ))}
        </div>
      </div>

      <section className="mt-6 border-t border-border pt-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div><h3 className="font-bold">رنگ‌های محصول</h3><p className="mt-1 text-xs text-muted-foreground">برای هر رنگ یک کارت مستقل با کد عددی خودکار ساخته می‌شود.</p></div>
          <button type="button" className={secondary} onClick={() => { setColors(current => [...current, { key: nextKey, name: "", slug: "", hex_color: "#000000", sizes: [] }]); setNextKey(value => value + 1); }}>＋ افزودن رنگ</button>
        </div>
        <div className="space-y-4">
          {colors.map((color, index) => (
            <section key={color.key} className="rounded-xl border border-border p-4">
              <div className="mb-3 flex items-center justify-between gap-2"><h4 className="text-sm font-semibold">رنگ {index + 1}</h4>{colors.length > 1 && <button type="button" className={secondary} onClick={() => setColors(current => current.filter(item => item.key !== color.key))}>حذف رنگ</button>}</div>
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="text-sm">نام رنگ<input required maxLength={60} value={color.name} onChange={event => updateColor(index, { name: event.target.value })} className={field} placeholder="مثلاً آبی آسمانی" /></label>
                <label className="text-sm">شناسه انگلیسی رنگ<input required maxLength={80} value={color.slug} onChange={event => updateColor(index, { slug: event.target.value })} className={field} dir="ltr" placeholder="sky-blue" /></label>
                <label className="text-sm">کد رنگ<input type="color" value={color.hex_color} onChange={event => updateColor(index, { hex_color: event.target.value })} className={field + " h-11 p-1"} dir="ltr" /></label>
              </div>
              <div className="mt-4">
                <p className="mb-2 text-sm font-medium">سایزهای این رنگ و SKU</p>
                {sizes.length === 0 ? <p className="text-xs text-muted-foreground">ابتدا از مدیریت ساختار کاتالوگ، سایز تعریف کنید.</p> :
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {sizes.map(size => {
                      const selectedSize = color.sizes.find(item => item.size === size.id);
                      return <div key={size.id} className="rounded-lg border border-border p-3">
                        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(selectedSize)} onChange={event => toggleSize(index, size.id, event.target.checked)} />{size.label}</label>
                        {selectedSize && <label className="mt-2 block text-xs">SKU<input required maxLength={64} value={selectedSize.sku} onChange={event => updateSku(index, size.id, event.target.value)} className={field} dir="ltr" placeholder="مثلاً KNIT-BLUE-M" /></label>}
                      </div>;
                    })}
                  </div>}
              </div>
            </section>
          ))}
        </div>
      </section>

      {error && <p role="alert" className="mt-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</p>}
      <div className="mt-5 flex flex-wrap gap-2"><button disabled={saving} className={primary}>{saving ? "در حال ساخت محصول و ترکیب‌ها…" : "ساخت محصول و همه رنگ‌ها و سایزها"}</button></div>
    </form>
  );
}
