"use client";

import { useState, type FormEvent } from "react";
import { apiRequest, apiUploadRequest, BrowserApiError } from "@/lib/browser-api";

type ProductField = { key: string; label: string; type: "text" | "number"; unit: string; required: boolean };
type Category = { id: number; name: string; is_active: boolean; product_fields: ProductField[] };
type Collection = { id: number; name: string; is_active: boolean };
type Size = { id: number; code: string; label: string; position: number };
type Product = {
  id: number; product_code: string | null; name: string; slug: string; description: string;
  price: string; sale_price: string | null; category: number; collections: number[]; is_active: boolean;
  colors: { id: number; name: string; slug: string }[];
};
type ColorDraft = {
  key: number; name: string; slug: string; hex_color: string;
  sizes: { size: number; sku: string }[];
  imageFiles: File[];
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
  onCreated: (product: Product, imagesUploaded: boolean) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [salePrice, setSalePrice] = useState("");
  const [categoryId, setCategoryId] = useState(String(categories.find(item => item.is_active)?.id ?? ""));
  const [collectionIds, setCollectionIds] = useState<number[]>([]);
  const [attributes, setAttributes] = useState<Record<string, string>>({});
  const [colors, setColors] = useState<ColorDraft[]>([
    { key: 1, name: "", slug: "", hex_color: "#000000", sizes: [], imageFiles: [] },
  ]);
  const [nextKey, setNextKey] = useState(2);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const selectedCategory = categories.find(item => item.id === Number(categoryId));

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

  function setColorImages(colorIndex: number, imageFiles: File[]) {
    setColors(current => current.map((color, index) => index === colorIndex ? { ...color, imageFiles } : color));
  }

  function moveColorImage(colorIndex: number, imageIndex: number, delta: number) {
    setColors(current => current.map((color, index) => {
      if (index !== colorIndex) return color;
      const target = imageIndex + delta;
      if (target < 0 || target >= color.imageFiles.length) return color;
      const imageFiles = [...color.imageFiles];
      [imageFiles[imageIndex], imageFiles[target]] = [imageFiles[target], imageFiles[imageIndex]];
      return { ...color, imageFiles };
    }));
  }

  function removeColorImage(colorIndex: number, imageIndex: number) {
    setColors(current => current.map((color, index) => index === colorIndex
      ? { ...color, imageFiles: color.imageFiles.filter((_, fileIndex) => fileIndex !== imageIndex) }
      : color));
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
        attributes: Object.fromEntries(Object.entries(attributes).map(([key, value]) => [key, value.trim() === "//" ? "" : value.trim()])),
        colors: colors.map(color => ({
          name: color.name.trim(),
          slug: color.slug.trim(),
          hex_color: color.hex_color,
          sizes: color.sizes.map(item => ({ size: item.size, sku: item.sku.trim() })),
        })),
      });

      let imagesUploaded = true;
      try {
        for (let colorIndex = 0; colorIndex < product.colors.length; colorIndex += 1) {
          const createdColor = product.colors[colorIndex];
          const draft = colors[colorIndex];
          for (let imageIndex = 0; imageIndex < draft.imageFiles.length; imageIndex += 1) {
            const body = new FormData();
            body.append("variant", String(createdColor.id));
            body.append("file", draft.imageFiles[imageIndex]);
            body.append("alt_text", `${product.name} · ${createdColor.name} · تصویر ${imageIndex + 1}`);
            await apiUploadRequest("/api/admin/catalog/images/upload/", body);
          }
        }
      } catch {
        // The product already exists; never invite a retry that would create a duplicate product.
        imagesUploaded = false;
      }
      await onCreated(product, imagesUploaded);
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
        <label className="text-sm">دسته‌بندی<select required value={categoryId} onChange={event => {
          const nextId = Number(event.target.value);
          setCategoryId(event.target.value);
          const nextCategory = categories.find(item => item.id === nextId);
          setAttributes(old => Object.fromEntries((nextCategory?.product_fields ?? []).map(definition => [definition.key, old[definition.key] ?? ""])));
        }} className={field}><option value="">انتخاب دسته‌بندی</option>{categories.filter(item => item.is_active).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="text-sm">قیمت اصلی (تومان)<input required type="number" min="1" step="1" value={price} onChange={event => setPrice(event.target.value)} className={field} dir="ltr" /></label>
        <label className="text-sm">قیمت با تخفیف (اختیاری)<input type="number" min="1" step="1" value={salePrice} onChange={event => setSalePrice(event.target.value)} className={field} dir="ltr" /></label>
        <label className="text-sm sm:col-span-2 lg:col-span-1">توضیحات<textarea value={description} onChange={event => setDescription(event.target.value)} rows={2} className={field} /></label>
      </div>

      {(selectedCategory?.product_fields ?? []).length > 0 && (
        <section className="mt-5 rounded-xl border border-border p-4">
          <h3 className="font-semibold">مشخصات اختصاصی این دسته‌بندی</h3>
          <p className="mt-1 text-xs text-muted-foreground">فقط فیلدهای تعریف‌شده برای «{selectedCategory?.name}» نمایش داده می‌شوند.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {selectedCategory?.product_fields.map(definition => (
              <label key={definition.key} className="text-sm">
                {definition.label}{definition.unit ? ` (${definition.unit})` : ""}{definition.required ? " *" : ""}
                <input
                  type={definition.type === "number" ? "number" : "text"}
                  step={definition.type === "number" ? "any" : undefined}
                  required={definition.required}
                  value={attributes[definition.key] ?? ""}
                  onChange={event => setAttributes(old => ({ ...old, [definition.key]: event.target.value }))}
                  className={field}
                />
              </label>
            ))}
          </div>
        </section>
      )}

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
          <button type="button" className={secondary} onClick={() => { setColors(current => [...current, { key: nextKey, name: "", slug: "", hex_color: "#000000", sizes: [], imageFiles: [] }]); setNextKey(value => value + 1); }}>＋ افزودن رنگ</button>
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
              <div className="mt-5 border-t border-border pt-4">
                <label className="block text-sm font-medium">تصاویر این رنگ (اختیاری)
                  <input
                    type="file"
                    multiple
                    accept="image/jpeg,image/png,image/webp"
                    disabled={saving}
                    className={field}
                    onChange={(event) => {
                      const files = Array.from(event.currentTarget.files ?? []);
                      event.currentTarget.value = "";
                      const invalid = files.find(file =>
                        file.size <= 0 ||
                        file.size > 8 * 1024 * 1024 ||
                        !["image/jpeg", "image/png", "image/webp"].includes(file.type)
                      );
                      if (invalid) {
                        setError("هر تصویر باید JPEG، PNG یا WebP و حداکثر ۸ مگابایت باشد.");
                        return;
                      }
                      setError("");
                      setColorImages(index, files);
                    }}
                  />
                </label>
                {color.imageFiles.length > 0 && (
                  <ol className="mt-3 space-y-2">
                    {color.imageFiles.map((file, imageIndex) => (
                      <li key={`${file.name}-${file.size}-${imageIndex}`} className="flex flex-wrap items-center gap-2 rounded-lg border border-border px-3 py-2">
                        <span className="min-w-0 flex-1 truncate text-xs">{imageIndex + 1}. {file.name}</span>
                        <button type="button" className={secondary} disabled={saving || imageIndex === 0} onClick={() => moveColorImage(index, imageIndex, -1)}>بالا</button>
                        <button type="button" className={secondary} disabled={saving || imageIndex === color.imageFiles.length - 1} onClick={() => moveColorImage(index, imageIndex, 1)}>پایین</button>
                        <button type="button" className={secondary} disabled={saving} onClick={() => removeColorImage(index, imageIndex)}>حذف</button>
                      </li>
                    ))}
                  </ol>
                )}
                <p className="mt-2 text-xs text-muted-foreground">تصاویر پس از ایجاد محصول به همین ترتیب به گالری رنگ اضافه می‌شوند؛ تصویر اول، تصویر اصلی کارت محصول خواهد بود.</p>
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
