"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";
import VariantImageManager from "./VariantImageManager";
import ProductMeasurementManager from "./ProductMeasurementManager";
import InventoryHistory from "./InventoryHistory";
import CatalogTaxonomyManager from "./CatalogTaxonomyManager";
import CreateProductWithVariantsForm from "./CreateProductWithVariantsForm";

type Page<T> = { results: T[]; next: string | null; count: number };
type Category = { id: number; name: string; slug: string; is_active: boolean; position: number };
type Collection = { id: number; name: string; slug: string; is_active: boolean; position: number };
type Size = { id: number; code: string; label: string; position: number };
type Product = { id: number; product_code: string | null; name: string; slug: string; description: string; price: string; sale_price: string | null; category: number; collections: number[]; is_active: boolean };
type Color = { id: number; product: number; name: string; slug: string; product_code: string; hex_color: string; is_active: boolean; position: number };
type VariantSize = { id: number; variant: number; size: number; sku: string; stock_quantity: number; is_active: boolean };
type Adjustment = { id: number; variant_size: number; quantity_change: number; stock_after: number; reason: string; created_at: string };

const inputClass = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary";
const buttonClass = "rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondaryClass = "rounded-xl border border-border px-4 py-2.5 text-sm hover:bg-muted disabled:opacity-50";

async function getAll<T>(path: string): Promise<T[]> {
  const rows: T[] = [];
  let next: string | null = path;
  let pages = 0;
  while (next && pages < 40) {
    const page: Page<T> = await apiRequest<Page<T>>("GET", next);
    rows.push(...page.results);
    next = page.next ? new URL(page.next, window.location.origin).pathname + new URL(page.next, window.location.origin).search : null;
    pages += 1;
  }
  return rows;
}

function errorMessage(error: unknown): string {
  if (error instanceof BrowserApiError) {
    if (error.status === 401 || error.status === 403) return "دسترسی کافی برای این عملیات ندارید. مجوزهای مدل Django را بررسی کنید.";
    if (error.status === 400) return "اطلاعات واردشده معتبر نیست یا با یک رکورد موجود تداخل دارد.";
    if (error.status === 0) return "ارتباط با سرور برقرار نشد.";
  }
  return "انجام عملیات با خطا مواجه شد. اطلاعات را بررسی و دوباره تلاش کنید.";
}

export default function AdminCatalogPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [sizes, setSizes] = useState<Size[]>([]);
  const [colors, setColors] = useState<Color[]>([]);
  const [variantSizes, setVariantSizes] = useState<VariantSize[]>([]);
  const [selected, setSelected] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [salePrice, setSalePrice] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [collectionIds, setCollectionIds] = useState<number[]>([]);
  const [colorName, setColorName] = useState("");
  const [colorSlug, setColorSlug] = useState("");
  const [hexColor, setHexColor] = useState("#000000");
  const [editingColorId, setEditingColorId] = useState<number | null>(null);
  const [variantId, setVariantId] = useState<number | null>(null);
  const [sizeId, setSizeId] = useState("");
  const [sku, setSku] = useState("");
  const [stockChanges, setStockChanges] = useState<Record<number, string>>({});
  const [stockReasons, setStockReasons] = useState<Record<number, string>>({});

  const loadCatalog = useCallback(async () => {
    const [p, c, co, s, v, vs] = await Promise.all([
      getAll<Product>("/api/admin/catalog/products/"),
      getAll<Category>("/api/admin/catalog/categories/"),
      getAll<Collection>("/api/admin/catalog/collections/"),
      getAll<Size>("/api/admin/catalog/sizes/"),
      getAll<Color>("/api/admin/catalog/colors/"),
      getAll<VariantSize>("/api/admin/catalog/variant-sizes/"),
    ]);
    return { products: p, categories: c, collections: co, sizes: s, colors: v, variantSizes: vs };
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await loadCatalog();
      setProducts(data.products);
      setCategories(data.categories);
      setCollections(data.collections);
      setSizes(data.sizes);
      setColors(data.colors);
      setVariantSizes(data.variantSizes);
      setSelected((current) => current ? data.products.find((item) => item.id === current.id) ?? null : null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [loadCatalog]);

  useEffect(() => {
    let cancelled = false;
    void loadCatalog().then((data) => {
      if (cancelled) return;
      setProducts(data.products);
      setCategories(data.categories);
      setCollections(data.collections);
      setSizes(data.sizes);
      setColors(data.colors);
      setVariantSizes(data.variantSizes);
      setLoading(false);
    }).catch((e: unknown) => {
      if (!cancelled) setError(errorMessage(e));
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [loadCatalog]);

  const visibleProducts = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    return products.filter((p) => !term || p.name.toLocaleLowerCase().includes(term) || String(p.product_code ?? "").includes(term));
  }, [products, search]);

  const selectedColors = selected ? colors.filter((color) => color.product === selected.id) : [];
  const formatPrice = (value: string | number) => Number(value).toLocaleString("fa-IR") + " تومان";

  function resetProductForm(product?: Product) {
    setName(product?.name ?? "");
    setSlug(product?.slug ?? "");
    setDescription(product?.description ?? "");
    setPrice(product?.price ?? "");
    setSalePrice(product?.sale_price ?? "");
    setCategoryId(String(product?.category ?? categories.find((c) => c.is_active)?.id ?? ""));
    setCollectionIds(product?.collections ?? []);
    setShowForm(true);
    setError("");
  }

  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true); setError(""); setNotice("");
    const payload = { name, slug, description, price, sale_price: salePrice || null, category: Number(categoryId), collections: collectionIds };
    try {
      const saved = selected && showForm
        ? await apiRequest<Product>("PATCH", `/api/admin/catalog/products/${selected.id}/`, payload)
        : await apiRequest<Product>("POST", "/api/admin/catalog/products/", payload);
      setShowForm(false);
      setNotice("اطلاعات محصول ذخیره شد.");
      await refresh();
      setSelected(saved);
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  async function toggleProduct(product: Product) {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<Product>("PATCH", `/api/admin/catalog/products/${product.id}/`, { is_active: !product.is_active });
      setNotice(product.is_active ? "محصول از فروشگاه خارج شد." : "محصول منتشر شد.");
      await refresh();
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  async function addColor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<Color>(editingColorId ? "PATCH" : "POST", editingColorId ? `/api/admin/catalog/colors/${editingColorId}/` : "/api/admin/catalog/colors/", { product: selected.id, name: colorName, slug: colorSlug, hex_color: hexColor, position: editingColorId ? (selectedColors.find((item) => item.id === editingColorId)?.position ?? selectedColors.length) : selectedColors.length, ...(editingColorId ? {} : { is_active: true }) });
      setColorName(""); setColorSlug(""); setHexColor("#000000"); setEditingColorId(null);
      setNotice(editingColorId ? "مشخصات رنگ ویرایش شد." : "رنگ جدید اضافه شد؛ کد کارت به‌صورت خودکار ساخته می‌شود.");
      await refresh();
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  async function toggleColor(color: Color) {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<Color>("PATCH", `/api/admin/catalog/colors/${color.id}/`, { is_active: !color.is_active });
      setNotice(color.is_active ? "رنگ غیرفعال شد؛ اطلاعات و سابقه آن حفظ شد." : "رنگ دوباره فعال شد.");
      await refresh();
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  async function toggleVariantSize(item: VariantSize) {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<VariantSize>("PATCH", `/api/admin/catalog/variant-sizes/${item.id}/`, { is_active: !item.is_active });
      setNotice(item.is_active ? "ترکیب رنگ و سایز غیرفعال شد؛ موجودی و سوابق حفظ شدند." : "ترکیب رنگ و سایز دوباره فعال شد.");
      await refresh();
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  async function addVariantSize(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!variantId) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const created = await apiRequest<VariantSize>("POST", "/api/admin/catalog/variant-sizes/", { variant: variantId, size: Number(sizeId), sku, is_active: true });
      setSizeId(""); setSku("");
      setVariantId(created.variant);
      setNotice("سایز به رنگ اضافه شد. برای ثبت موجودی اولیه از فرم گردش موجودی استفاده کنید.");
      await refresh();
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  async function adjustStock(event: FormEvent<HTMLFormElement>, item: VariantSize) {
    event.preventDefault();
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<Adjustment>("POST", "/api/admin/inventory/adjustments/", { variant_size: item.id, quantity_change: Number(stockChanges[item.id]), reason: stockReasons[item.id] });
      setStockChanges((old) => ({ ...old, [item.id]: "" }));
      setStockReasons((old) => ({ ...old, [item.id]: "" }));
      setNotice("گردش موجودی با موفقیت ثبت شد.");
      await refresh();
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  return (
    <main dir="rtl" className="mx-auto w-full max-w-7xl px-4 py-8 sm:py-10">
      <div className="mb-7 flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
          <h1 className="mt-3 text-2xl font-bold sm:text-3xl">مدیریت محصولات</h1>
          <p className="mt-2 text-sm text-muted-foreground">محصول، رنگ، سایز و موجودی هر ترکیب را از یک صفحه مدیریت کنید.</p>
        </div>
        <button type="button" className={buttonClass} onClick={() => { setSelected(null); setShowForm(true); setError(""); setNotice(""); }}>＋ محصول جدید</button>
      </div>

      <CatalogTaxonomyManager />

      {notice && <div role="status" className="mb-4 rounded-xl border border-border bg-muted p-3 text-sm">{notice}</div>}
      {error && <div role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</div>}

      {showForm && !selected && <CreateProductWithVariantsForm
        categories={categories}
        collections={collections}
        sizes={sizes}
        onCancel={() => setShowForm(false)}
        onCreated={async (product) => {
          setShowForm(false);
          setNotice("محصول و همه رنگ‌ها و سایزهای انتخاب‌شده به‌صورت یکپارچه ساخته شدند.");
          await refresh();
          setSelected(product);
        }}
      />}
      {showForm && selected && (
        <form onSubmit={saveProduct} className="mb-7 rounded-2xl border border-border bg-card p-5 sm:p-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <h2 className="text-lg font-bold">{selected ? "ویرایش محصول" : "ثبت محصول جدید"}</h2>
            <button type="button" className={secondaryClass} onClick={() => setShowForm(false)}>انصراف</button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="text-sm">نام محصول<input required value={name} onChange={(e) => setName(e.target.value)} className={inputClass} /></label>
            <label className="text-sm">شناسه انگلیسی (Slug)<input required value={slug} onChange={(e) => setSlug(e.target.value)} dir="ltr" className={inputClass} /></label>
            <label className="text-sm">دسته‌بندی<select required value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className={inputClass}><option value="">انتخاب دسته‌بندی</option>{categories.filter((c) => c.is_active).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
            <label className="text-sm">قیمت اصلی (تومان)<input required type="number" min="1" step="1" value={price} onChange={(e) => setPrice(e.target.value)} className={inputClass} dir="ltr" /></label>
            <label className="text-sm">قیمت با تخفیف (اختیاری)<input type="number" min="1" step="1" value={salePrice} onChange={(e) => setSalePrice(e.target.value)} className={inputClass} dir="ltr" /></label>
            <label className="text-sm sm:col-span-2 lg:col-span-1">توضیحات<textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className={inputClass} /></label>
          </div>
          <div className="mt-4">
            <p className="mb-2 text-sm">مجموعه‌ها</p>
            <div className="flex flex-wrap gap-2">{collections.filter((c) => c.is_active).map((c) => <label key={c.id} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm"><input type="checkbox" checked={collectionIds.includes(c.id)} onChange={(e) => setCollectionIds((old) => e.target.checked ? [...old, c.id] : old.filter((id) => id !== c.id))} />{c.name}</label>)}</div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2"><button disabled={saving} className={buttonClass}>{saving ? "در حال ذخیره…" : "ذخیره محصول"}</button></div>
        </form>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(300px,0.85fr)_minmax(0,1.5fr)]">
        <section className="min-w-0 rounded-2xl border border-border bg-card p-4 sm:p-5">
          <div className="mb-4 flex items-center justify-between gap-3"><h2 className="font-bold">فهرست محصولات</h2><span className="text-xs text-muted-foreground">{products.length.toLocaleString("fa-IR")} محصول</span></div>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجو با نام یا کد محصول…" className={inputClass + " mb-4"} />
          {loading ? <p className="py-8 text-center text-sm text-muted-foreground">در حال دریافت اطلاعات…</p> : visibleProducts.length === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">محصولی پیدا نشد.</p> : (
            <div className="max-h-[70vh] space-y-2 overflow-y-auto">
              {visibleProducts.map((product) => <button key={product.id} type="button" onClick={() => { setSelected(product); setShowForm(false); setVariantId(null); setError(""); }} className={"w-full rounded-xl border p-3 text-right transition " + (selected?.id === product.id ? "border-primary bg-muted" : "border-border hover:bg-muted/60")}>
                <span className="flex items-center justify-between gap-2"><strong className="text-sm">{product.name}</strong><span className={"shrink-0 rounded-full px-2 py-1 text-[11px] " + (product.is_active ? "bg-muted text-foreground" : "bg-destructive/10 text-destructive")}>{product.is_active ? "منتشر" : "پیش‌نویس"}</span></span>
                <span className="mt-2 flex flex-wrap gap-x-3 text-xs text-muted-foreground"><span>کد: {product.product_code || "—"}</span><span>{formatPrice(product.sale_price || product.price)}</span></span>
              </button>)}
            </div>
          )}
        </section>

        <section className="min-w-0">
          {!selected ? <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-border p-6 text-center"><span className="text-3xl">▦</span><h2 className="mt-3 font-semibold">یک محصول انتخاب کنید</h2><p className="mt-2 text-sm text-muted-foreground">یا محصول جدیدی بسازید تا رنگ‌ها و سایزهای آن را مدیریت کنید.</p></div> : (
            <div className="space-y-5">
              <section className="rounded-2xl border border-border bg-card p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><p className="text-xs text-muted-foreground">محصول انتخاب‌شده</p><h2 className="mt-1 text-xl font-bold">{selected.name}</h2><p className="mt-1 text-xs text-muted-foreground">کد محصول: {selected.product_code || "—"} · {formatPrice(selected.sale_price || selected.price)}</p></div>
                  <div className="flex flex-wrap gap-2"><button type="button" className={secondaryClass} onClick={() => resetProductForm(selected)}>ویرایش مشخصات</button><button type="button" disabled={saving} className={secondaryClass} onClick={() => void toggleProduct(selected)}>{selected.is_active ? "خروج از انتشار" : "انتشار محصول"}</button></div>
                </div>
              </section>

              <ProductMeasurementManager
                productId={selected.id}
                sizes={sizes}
                colors={selectedColors}
                variantSizes={variantSizes.filter((item) => selectedColors.some((color) => color.id === item.variant))}
              />

              <section className="rounded-2xl border border-border bg-card p-5">
                <h3 className="font-bold">رنگ‌های محصول</h3>
                <p className="mt-1 text-xs text-muted-foreground">برای هر رنگ یک کارت مستقل ساخته می‌شود؛ کد عددی کارت را سیستم خودکار اختصاص می‌دهد.</p>
                <form onSubmit={addColor} className="mt-4 grid gap-3 sm:grid-cols-2">
                  <label className="text-sm">نام رنگ<input required value={colorName} onChange={(e) => setColorName(e.target.value)} className={inputClass} placeholder="مثلاً آبی آسمانی" /></label>
                  <label className="text-sm">شناسه انگلیسی رنگ<input required value={colorSlug} onChange={(e) => setColorSlug(e.target.value)} className={inputClass} dir="ltr" placeholder="sky-blue" /></label>
                  <label className="text-sm">کد رنگ<input type="color" value={hexColor} onChange={(e) => setHexColor(e.target.value)} className={inputClass + " h-11 p-1"} dir="ltr" /></label>
                  <div className="flex items-end gap-2"><button disabled={saving} className={buttonClass}>{editingColorId ? "ذخیره رنگ" : "افزودن رنگ"}</button>{editingColorId && <button type="button" className={secondaryClass} onClick={() => { setEditingColorId(null); setColorName(""); setColorSlug(""); setHexColor("#000000"); }}>لغو</button>}</div>
                </form>
                <div className="mt-4 space-y-2">
                  {selectedColors.map((color) => <div key={color.id} className="rounded-xl border border-border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <button type="button" onClick={() => setVariantId(color.id)} className="flex items-center gap-3 text-right"><span className="size-8 rounded-full border border-border" style={{ backgroundColor: color.hex_color || "#ddd" }} /><span><strong className="block text-sm">{color.name}</strong><span className="text-xs text-muted-foreground">کد کارت: {color.product_code}</span></span></button>
                      <div className="flex flex-wrap gap-2">
                        <button type="button" className={secondaryClass} onClick={() => { setEditingColorId(color.id); setColorName(color.name); setColorSlug(color.slug); setHexColor(color.hex_color || "#000000"); }}>ویرایش رنگ</button>
                        <button type="button" disabled={saving} className={secondaryClass} onClick={() => void toggleColor(color)}>{color.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}</button>
                        <button type="button" className={variantId === color.id ? buttonClass : secondaryClass} onClick={() => setVariantId(color.id)}>مدیریت سایزها</button>
                      </div>
                    </div>
                    {variantId === color.id && <div className="mt-4 border-t border-border pt-4">
                      <form onSubmit={addVariantSize} className="grid gap-3 sm:grid-cols-3">
                        <label className="text-sm">سایز<select required value={sizeId} onChange={(e) => setSizeId(e.target.value)} className={inputClass}><option value="">انتخاب سایز</option>{sizes.filter((s) => !variantSizes.some((vs) => vs.variant === color.id && vs.size === s.id)).map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
                        <label className="text-sm">SKU<input required value={sku} onChange={(e) => setSku(e.target.value)} className={inputClass} dir="ltr" /></label>
                        <div className="flex items-end"><button disabled={saving} className={buttonClass}>افزودن سایز</button></div>
                      </form>
                      <div className="mt-4 space-y-3">
                        {variantSizes.filter((vs) => vs.variant === color.id).map((item) => {
                          const size = sizes.find((s) => s.id === item.size);
                          return <div key={item.id} className="rounded-xl bg-muted/50 p-3">
                            <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><strong>{size?.label || "سایز نامشخص"}{!item.is_active && <span className="mr-2 text-xs text-destructive">غیرفعال</span>}</strong><span className="flex items-center gap-3">موجودی: <b>{item.stock_quantity.toLocaleString("fa-IR")}</b><button type="button" disabled={saving} className={secondaryClass} onClick={() => void toggleVariantSize(item)}>{item.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}</button></span></div>
                            <form onSubmit={(e) => void adjustStock(e, item)} className="mt-3 grid gap-2 sm:grid-cols-[110px_1fr_auto]">
                              <label className="text-xs">تغییر تعداد<input required type="number" step="1" value={stockChanges[item.id] ?? ""} onChange={(e) => setStockChanges((old) => ({ ...old, [item.id]: e.target.value }))} className={inputClass} dir="ltr" placeholder="+10 / -2" /></label>
                              <label className="text-xs">دلیل تغییر<input required value={stockReasons[item.id] ?? ""} onChange={(e) => setStockReasons((old) => ({ ...old, [item.id]: e.target.value }))} className={inputClass} placeholder="مثلاً ورود بار جدید" /></label>
                              <div className="flex items-end"><button disabled={saving || !stockChanges[item.id] || Number(stockChanges[item.id]) === 0 || !stockReasons[item.id]?.trim()} className={secondaryClass}>ثبت گردش</button></div>
                            </form>
                            <InventoryHistory variantSizeId={item.id} />
                          </div>;
                        })}
                        {variantSizes.filter((vs) => vs.variant === color.id).length === 0 && <p className="text-xs text-muted-foreground">هنوز سایزی برای این رنگ ثبت نشده است.</p>}
                      </div>
                      <VariantImageManager variantId={color.id} />
                    </div>}
                  </div>)}
                  {selectedColors.length === 0 && <p className="rounded-xl bg-muted p-4 text-sm text-muted-foreground">هنوز رنگی برای این محصول ثبت نشده است.</p>}
                </div>
              </section>
            </div>
          )}
        </section>
      </div>
      <p className="mt-7 text-xs leading-6 text-muted-foreground">تغییر موجودی فقط از مسیر ثبت گردش حسابرسی‌شده انجام می‌شود. تصاویر هر رنگ جداگانه مدیریت می‌شوند و اولین تصویر، تصویر اصلی کارت محصول است.</p>
    </main>
  );
}
