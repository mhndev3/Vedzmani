"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import Image from "next/image";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";
import VariantImageManager from "./VariantImageManager";
import ProductMeasurementManager from "./ProductMeasurementManager";
import InventoryHistory from "./InventoryHistory";
import CreateProductWithVariantsForm from "./CreateProductWithVariantsForm";

type Page<T> = { results: T[]; next: string | null; count: number };
type ProductField = { key: string; label: string; type: "text" | "number"; unit: string; required: boolean };
type Category = { id: number; name: string; slug: string; is_active: boolean; position: number; product_fields: ProductField[]; sizes: number[] };
type Collection = { id: number; name: string; slug: string; is_active: boolean; position: number };
type Size = { id: number; code: string; label: string; position: number };
type Product = { id: number; product_code: string | null; name: string; slug: string; description: string; attributes: Record<string, string>; price: string; sale_price: string | null; category: number; collections: number[]; is_active: boolean };
type Color = { id: number; product: number; name: string; slug: string; product_code: string; hex_color: string; is_active: boolean; position: number };
type VariantSize = { id: number; variant: number; size: number; sku: string; stock_quantity: number; is_active: boolean };
type Adjustment = { id: number; variant_size: number; quantity_change: number; stock_after: number; reason: string; created_at: string };
type AdminImage = { id: number; variant: number; url: string; alt_text: string; position: number; is_primary: boolean; is_active: boolean };
type ImageDraft = { variant: number; image_ids: number[]; deactivate_ids: number[] };
type NewColorDraft = { key: string; name: string; hex_color: string; sizes: { size: number; initial_stock: number }[] };
type NewVariantSizeDraft = { key: string; variant: number; size: number; initial_stock: number };

const inputClass = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary";
const buttonClass = "rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondaryClass = "rounded-xl border border-border px-4 py-2.5 text-sm hover:bg-muted disabled:opacity-50";

async function getAll<T>(path: string): Promise<T[]> {
  const rows: T[] = [];
  let next: string | null = path;
  const visited = new Set<string>();
  while (next) {
    if (visited.has(next) || visited.size >= 10000) {
      throw new Error("Catalog pagination did not terminate.");
    }
    visited.add(next);
    const page: Page<T> = await apiRequest<Page<T>>("GET", next);
    rows.push(...page.results);
    next = page.next ? new URL(page.next, window.location.origin).pathname + new URL(page.next, window.location.origin).search : null;
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
  const [images, setImages] = useState<AdminImage[]>([]);
  const [imageDrafts, setImageDrafts] = useState<Record<number, ImageDraft>>({});
  const [newColorDrafts, setNewColorDrafts] = useState<NewColorDraft[]>([]);
  const [newVariantSizeDrafts, setNewVariantSizeDrafts] = useState<NewVariantSizeDraft[]>([]);
  const [newColorSizeSelections, setNewColorSizeSelections] = useState<Record<string, string>>({});
  const [newColorSizeStocks, setNewColorSizeStocks] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [productFormMode, setProductFormMode] = useState<"create" | "edit" | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [salePrice, setSalePrice] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [collectionIds, setCollectionIds] = useState<number[]>([]);
  const [attributes, setAttributes] = useState<Record<string, string>>({});
  const [colorName, setColorName] = useState("");
  const [hexColor, setHexColor] = useState("#000000");
  const [editingColorId, setEditingColorId] = useState<number | null>(null);
  const [variantId, setVariantId] = useState<number | null>(null);
  const [imageVariantId, setImageVariantId] = useState<number | null>(null);
  const [sizeId, setSizeId] = useState("");
  const [newVariantSizeStock, setNewVariantSizeStock] = useState("0");
  const [stockChanges, setStockChanges] = useState<Record<number, string>>({});
  const [skuDrafts, setSkuDrafts] = useState<Record<number, string>>({});
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
    const imageRows = await getAll<AdminImage>("/api/admin/catalog/images/").catch(() => []);
    return { products: p, categories: c, collections: co, sizes: s, colors: v, variantSizes: vs, images: imageRows };
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
      setImages(data.images);
      setSelected((current) => current ? data.products.find((item) => item.id === current.id) ?? null : null);
      return data;
    } catch (e) {
      setError(errorMessage(e));
      return null;
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
      setImages(data.images);
      const requestedMode = new URLSearchParams(window.location.search).get("mode");
      if (requestedMode === "create") {
        setSelected(null);
        setProductFormMode("create");
      } else if (requestedMode === "edit") {
        setProductFormMode(null);
      }
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

  const selectedColors = selected ? colors.filter((color) => color.product === selected.id).sort((a, b) => a.position - b.position || a.id - b.id) : [];
  const selectedCategory = selected ? categories.find((category) => category.id === selected.category) : undefined;
  const activeEditFieldKeys = new Set((categories.find((category) => category.id === Number(categoryId))?.product_fields ?? []).map((field) => field.key));
  const legacyAttributes = selected ? Object.entries(selected.attributes ?? {}).filter(([key]) => !activeEditFieldKeys.has(key)) : [];
  const editableSizeIds = new Set([
    ...(selectedCategory?.sizes ?? []),
    ...variantSizes.filter((item) => selectedColors.some((color) => color.id === item.variant)).map((item) => item.size),
  ]);
  const formatPrice = (value: string | number) => Number(value).toLocaleString("fa-IR") + " تومان";
  const salePriceInvalid = salePrice.trim() !== "" && price.trim() !== "" && Number(salePrice) >= Number(price);

  function resetProductForm(product?: Product) {
    const nextCategoryId = product?.category ?? categories.find((c) => c.is_active)?.id ?? 0;
    const nextCategory = categories.find((category) => category.id === nextCategoryId);
    setName(product?.name ?? "");
    setDescription(product?.description ?? "");
    setPrice(product?.price ?? "");
    setSalePrice(product?.sale_price ?? "");
    setCategoryId(String(nextCategoryId || ""));
    setCollectionIds(product?.collections ?? []);
    setAttributes(Object.fromEntries((nextCategory?.product_fields ?? []).map(field => [
      field.key,
      product?.attributes?.[field.key] ?? "",
    ])));
    setProductFormMode("edit");
    setError("");
  }

  async function saveWorkspace(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!selected) return;

    const productPayload = productFormMode === "edit" ? {
      name,
      description: description.trim() === "//" ? "" : description,
      attributes: {
        ...Object.fromEntries(Object.entries(selected.attributes ?? {}).filter(([key]) => !activeEditFieldKeys.has(key))),
        ...Object.fromEntries(Object.entries(attributes).map(([key, value]) => [key, value.trim() === "//" ? "" : value.trim()])),
      },
      price,
      sale_price: salePrice || null,
      category: Number(categoryId),
      collections: collectionIds,
    } : {};

    if (productFormMode === "edit" && salePriceInvalid) {
      setError("قیمت با تخفیف باید کمتر از قیمت اصلی باشد.");
      return;
    }

    let draftValidationError = "";
    const pendingVariantSizes = variantSizes
      .filter((item) => selectedColors.some((color) => color.id === item.variant))
      .flatMap((item) => {
        const sku = (skuDrafts[item.id] ?? item.sku).trim();
        const rawChange = (stockChanges[item.id] ?? "").trim();
        if (!rawChange && (!sku || sku === item.sku)) return [];
        const change = rawChange ? Number(rawChange) : undefined;
        if (rawChange && (!Number.isInteger(change) || change === 0)) {
          draftValidationError = "تغییر موجودی باید عدد صحیح و غیرصفر باشد.";
          return [];
        }
        const reason = stockReasons[item.id]?.trim() ?? "";
        if (rawChange && !reason) {
          draftValidationError = "برای هر تغییر موجودی، دلیل الزامی است.";
          return [];
        }
        return [{
          id: item.id,
          ...(sku && sku !== item.sku ? { sku } : {}),
          ...(change !== undefined ? { quantity_change: change, stock_reason: reason } : {}),
        }];
      });

    if (draftValidationError) {
      setError(draftValidationError);
      return;
    }

    const pendingColors = editingColorId !== null ? [{
      id: editingColorId,
      name: colorName.trim(),
      hex_color: hexColor,
    }] : [];

    const invalidNewColor = newColorDrafts.some((color) => !color.name.trim() || color.sizes.some((item) => !Number.isInteger(item.initial_stock) || item.initial_stock < 0));
    const invalidNewVariantSize = newVariantSizeDrafts.some((item) => !Number.isInteger(item.initial_stock) || item.initial_stock < 0);
    if (invalidNewColor || invalidNewVariantSize) {
      setError("نام رنگ و موجودی اولیه سایزها را بررسی کنید. موجودی باید عدد صحیح و نامنفی باشد.");
      return;
    }

    if (pendingColors.some((color) => !color.name)) {
      setError("نام رنگ نمی‌تواند خالی باشد.");
      return;
    }

    setSaving(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<{
        product: Product;
        colors: Color[];
        variant_sizes: VariantSize[];
      }>("POST", `/api/admin/catalog/products/${selected.id}/workspace-save/`, {
        product: productPayload,
        colors: pendingColors,
        variant_sizes: pendingVariantSizes,
        new_colors: newColorDrafts.map(({ name, hex_color, sizes }) => ({ name: name.trim(), hex_color, sizes })),
        new_variant_sizes: newVariantSizeDrafts.map(({ variant, size, initial_stock }) => ({ variant, size, initial_stock })),
        images: Object.values(imageDrafts),
      });
      setProductFormMode(null);
      setEditingColorId(null);
      setColorName("");
      setHexColor("#000000");
      setSkuDrafts({});
      setStockChanges({});
      setStockReasons({});
      setImageDrafts({});
      setNewColorDrafts([]);
      setNewVariantSizeDrafts([]);
      setNewColorSizeSelections({});
      setNewColorSizeStocks({});
      setNewVariantSizeStock("0");
      setImageVariantId(null);
      setNotice("همه تغییرات پیش‌نویس محصول، رنگ‌ها، سایزها، موجودی و تصاویر ذخیره شدند.");
      await refresh();
      setSelected(result.product);
    } catch (e) {
      setError(e instanceof Error && !(e instanceof BrowserApiError) ? e.message : errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function toggleProductPublication() {
    if (!selected) return;
    const nextActive = !selected.is_active;
    if (selected.is_active && !window.confirm("این محصول از فروشگاه خارج شود؟ اطلاعات، رنگ‌ها، تصاویر و موجودی آن حفظ می‌شوند.")) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const saved = await apiRequest<Product>("PATCH", `/api/admin/catalog/products/${selected.id}/`, { is_active: nextActive });
      setNotice(nextActive
        ? "محصول منتشر شد."
        : "محصول از فروشگاه خارج شد؛ اطلاعات، رنگ‌ها، تصاویر و موجودی حفظ شدند.");
      await refresh();
      setSelected(saved);
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  async function addColor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    if (!colorName.trim()) {
      setError("نام رنگ نمی‌تواند خالی باشد.");
      return;
    }
    setNewColorDrafts((current) => [...current, {
      key: `new-color-${Date.now()}-${current.length}`,
      name: colorName.trim(),
      hex_color: hexColor,
      sizes: [],
    }]);
    setColorName("");
    setHexColor("#000000");
    setError("");
    setNotice("رنگ جدید به پیش‌نویس اضافه شد؛ با «ذخیره همه تغییرات» ثبت می‌شود.");
  }

  async function toggleColor(color: Color) {
    if (color.is_active && !window.confirm("این رنگ از فروشگاه غیرفعال شود؟ تصاویر، سایزها، موجودی و سوابق آن حذف نمی‌شوند و قابل بازگردانی هستند.")) return;
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<Color>("PATCH", `/api/admin/catalog/colors/${color.id}/`, { is_active: !color.is_active });
      setNotice(color.is_active ? "رنگ غیرفعال شد؛ اطلاعات و سابقه آن حفظ شد." : "رنگ دوباره فعال شد.");
      await refresh();
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(false); }
  }

  async function moveColor(color: Color, delta: number) {
    if (!selected) return;
    const ordered = [...selectedColors];
    const index = ordered.findIndex((item) => item.id === color.id);
    const target = index + delta;
    if (target < 0 || target >= ordered.length) return;
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<Color[]>("POST", "/api/admin/catalog/colors/reorder/", {
        product: selected.id,
        entry_ids: ordered.map((item) => item.id),
      });
      setNotice("ترتیب رنگ‌های این محصول به‌صورت یکپارچه ذخیره شد.");
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
      await refresh();
    } finally { setSaving(false); }
  }

  async function toggleVariantSize(item: VariantSize) {
    if (item.is_active && !window.confirm(`ترکیب این رنگ و سایز غیرفعال شود؟ موجودی فعلی (${item.stock_quantity}) و سوابق آن حفظ می‌شوند و با فعال‌سازی دوباره قابل استفاده خواهند بود.`)) return;
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
    if (!variantId || !sizeId) return;
    const initialStock = Number(newVariantSizeStock);
    if (!Number.isInteger(initialStock) || initialStock < 0) {
      setError("موجودی اولیه باید عدد صحیح و نامنفی باشد.");
      return;
    }
    if (newVariantSizeDrafts.some((item) => item.variant === variantId && item.size === Number(sizeId))) {
      setError("این سایز از قبل در پیش‌نویس این رنگ وجود دارد.");
      return;
    }
    setNewVariantSizeDrafts((current) => [...current, {
      key: `new-size-${Date.now()}-${current.length}`,
      variant: variantId,
      size: Number(sizeId),
      initial_stock: initialStock,
    }]);
    setSizeId("");
    setNewVariantSizeStock("0");
    setError("");
    setNotice("سایز جدید به پیش‌نویس اضافه شد؛ با ذخیره همه تغییرات ثبت می‌شود.");
  }

  function addSizeToNewColor(colorKey: string) {
    const size = Number(newColorSizeSelections[colorKey]);
    const initialStock = Number(newColorSizeStocks[colorKey] ?? "0");
    const color = newColorDrafts.find((item) => item.key === colorKey);
    if (!color || !size) return;
    if (!Number.isInteger(initialStock) || initialStock < 0) {
      setError("موجودی اولیه باید عدد صحیح و نامنفی باشد.");
      return;
    }
    if (color.sizes.some((item) => item.size === size)) {
      setError("این سایز قبلاً به پیش‌نویس رنگ اضافه شده است.");
      return;
    }
    setNewColorDrafts((current) => current.map((item) => item.key === colorKey
      ? { ...item, sizes: [...item.sizes, { size, initial_stock: initialStock }] }
      : item));
    setNewColorSizeSelections((current) => ({ ...current, [colorKey]: "" }));
    setNewColorSizeStocks((current) => ({ ...current, [colorKey]: "0" }));
    setError("");
  }

  return (
    <main dir="rtl" className="mx-auto w-full max-w-7xl px-4 py-8 sm:py-10">
      <div className="mb-7 flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
          <h1 className="mt-3 text-2xl font-bold sm:text-3xl">مدیریت محصولات</h1>
          <p className="mt-2 text-sm text-muted-foreground">محصول، رنگ، سایز و موجودی هر ترکیب را از یک صفحه مدیریت کنید.</p>
        </div>
        <button type="button" className={buttonClass} onClick={() => { setSelected(null); setProductFormMode("create"); setError(""); setNotice(""); }}>＋ محصول جدید</button>
      </div>

      {notice && <div role="status" className="mb-4 rounded-xl border border-border bg-muted p-3 text-sm">{notice}</div>}
      {error && <div role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</div>}

      {productFormMode === "create" && <CreateProductWithVariantsForm
        categories={categories}
        collections={collections}
        sizes={sizes}
        onCancel={() => setProductFormMode(null)}
        onCreated={async (product, imagesUploaded) => {
          setProductFormMode(null);
          setNotice(imagesUploaded
            ? "محصول، رنگ‌ها، سایزها و تصاویر انتخاب‌شده ساخته شدند."
            : "محصول و ترکیب‌های آن ساخته شدند، اما آپلود همه تصاویر کامل نشد. از بخش تصاویر رنگ‌ها ادامه دهید.");
          const data = await refresh();
          setSelected(product);
          setImageVariantId(data?.colors.find((color) => color.product === product.id)?.id ?? null);
        }}
      />}
      {productFormMode === "edit" && selected && (
        <form onSubmit={saveWorkspace} className="mb-7 rounded-2xl border border-border bg-card p-5 sm:p-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <h2 className="text-lg font-bold">{selected ? "ویرایش محصول" : "ثبت محصول جدید"}</h2>
            <button type="button" className={secondaryClass} onClick={() => setProductFormMode(null)}>انصراف</button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="text-sm">نام محصول<input required value={name} onChange={(e) => setName(e.target.value)} className={inputClass} /></label>
            <label className="text-sm">دسته‌بندی<select required value={categoryId} onChange={(event) => {
              const nextId = Number(event.target.value);
              setCategoryId(event.target.value);
              const nextCategory = categories.find(item => item.id === nextId);
              setAttributes(old => Object.fromEntries((nextCategory?.product_fields ?? []).map(field => [field.key, old[field.key] ?? ""])));
            }} className={inputClass}><option value="">انتخاب دسته‌بندی</option>{categories.filter((c) => c.is_active).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
            <label className="text-sm">قیمت اصلی (تومان)<input required type="number" min="1" step="1" value={price} onChange={(e) => setPrice(e.target.value)} className={inputClass} dir="ltr" /></label>
            <label className="text-sm">قیمت با تخفیف (اختیاری)<input type="number" min="1" step="1" value={salePrice} onChange={(e) => setSalePrice(e.target.value)} className={inputClass} dir="ltr" aria-invalid={salePriceInvalid} />{salePriceInvalid && <span className="mt-1 block text-xs text-destructive">قیمت با تخفیف باید کمتر از قیمت اصلی باشد.</span>}</label>
            <label className="text-sm sm:col-span-2 lg:col-span-1">توضیحات<textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className={inputClass} /></label>
          </div>
          {legacyAttributes.length > 0 && (
            <section className="mt-5 rounded-xl border border-border bg-muted/40 p-4">
              <h3 className="font-semibold">مشخصات حفظ‌شده از قبل</h3>
              <p className="mt-1 text-xs leading-6 text-muted-foreground">این مشخصات در دسته‌بندی فعلی تعریف نشده‌اند؛ هنگام ذخیره نیز همراه محصول حفظ می‌شوند.</p>
              <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                {legacyAttributes.map(([key, value]) => <div key={key} className="rounded-lg border border-border bg-background p-3"><dt className="text-xs text-muted-foreground">{key}</dt><dd className="mt-1 break-words text-sm">{String(value ?? "—") || "—"}</dd></div>)}
              </dl>
            </section>
          )}
          {(categories.find(item => item.id === Number(categoryId))?.product_fields ?? []).length > 0 && (
            <section className="mt-5 rounded-xl border border-border p-4">
              <h3 className="font-semibold">مشخصات اختصاصی این دسته‌بندی</h3>
              <p className="mt-1 text-xs text-muted-foreground">فقط فیلدهای تعریف‌شده برای دسته‌بندی انتخاب‌شده نمایش داده می‌شوند.</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {(categories.find(item => item.id === Number(categoryId))?.product_fields ?? []).map(definition => (
                  <label key={definition.key} className="text-sm">
                    {definition.label}{definition.unit ? ` (${definition.unit})` : ""}{definition.required ? " *" : ""}
                    <input
                      type={definition.type === "number" ? "number" : "text"}
                      step={definition.type === "number" ? "any" : undefined}
                      required={definition.required}
                      value={attributes[definition.key] ?? ""}
                      onChange={event => setAttributes(old => ({ ...old, [definition.key]: event.target.value }))}
                      className={inputClass}
                    />
                  </label>
                ))}
              </div>
            </section>
          )}
          <div className="mt-4">
            <p className="mb-2 text-sm">مجموعه‌ها</p>
            <div className="flex flex-wrap gap-2">{collections.filter((c) => c.is_active).map((c) => <label key={c.id} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm"><input type="checkbox" checked={collectionIds.includes(c.id)} onChange={(e) => setCollectionIds((old) => e.target.checked ? [...old, c.id] : old.filter((id) => id !== c.id))} />{c.name}</label>)}</div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2"><button disabled={saving || salePriceInvalid} className={buttonClass}>{saving ? "در حال ذخیره…" : "ذخیره همه تغییرات"}</button></div>
        </form>
      )}

      {productFormMode !== "create" && <div className="grid gap-6 lg:grid-cols-[minmax(300px,0.85fr)_minmax(0,1.5fr)]">
        <section className="min-w-0 rounded-2xl border border-border bg-card p-4 sm:p-5">
          <div className="mb-4 flex items-center justify-between gap-3"><h2 className="font-bold">فهرست محصولات</h2><span className="text-xs text-muted-foreground">{products.length.toLocaleString("fa-IR")} محصول</span></div>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجو با نام یا کد محصول…" className={inputClass + " mb-4"} />
          {loading ? <p className="py-8 text-center text-sm text-muted-foreground">در حال دریافت اطلاعات…</p> : visibleProducts.length === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">محصولی پیدا نشد.</p> : (
            <div className="max-h-[70vh] space-y-2 overflow-y-auto">
              {visibleProducts.map((product) => {
                const productColors = colors.filter((color) => color.product === product.id).sort((a, b) => a.position - b.position || a.id - b.id);
                const image = images.filter((item) => productColors.some((color) => color.id === item.variant)).sort((a, b) => {
                  const colorA = productColors.findIndex((color) => color.id === a.variant);
                  const colorB = productColors.findIndex((color) => color.id === b.variant);
                  return colorA - colorB || a.position - b.position || a.id - b.id;
                })[0];
                return <button key={product.id} type="button" onClick={() => { setSelected(product); setProductFormMode(null); setVariantId(null); setImageDrafts({}); setError(""); }} className={"w-full overflow-hidden rounded-xl border text-right transition " + (selected?.id === product.id ? "border-primary bg-muted" : "border-border hover:bg-muted/60")}>
                  <div className="flex gap-3 p-3">
                    <div className="relative size-20 shrink-0 overflow-hidden rounded-lg bg-muted">
                      {image ? <Image src={image.url} alt={image.alt_text || product.name} fill sizes="80px" className="object-cover" unoptimized /> : <div className="flex h-full items-center justify-center text-xs text-muted-foreground">بدون تصویر</div>}
                    </div>
                    <div className="min-w-0 flex-1">
                      <span className="flex items-start justify-between gap-2"><strong className="text-sm">{product.name}</strong><span className={"shrink-0 rounded-full px-2 py-1 text-[11px] " + (product.is_active ? "bg-muted text-foreground" : "bg-destructive/10 text-destructive")}>{product.is_active ? "منتشر" : "پیش‌نویس"}</span></span>
                      <span className="mt-2 block text-xs text-muted-foreground">کد محصول: {product.product_code || "—"}</span>
                      <span className="mt-1 flex flex-wrap items-center gap-2 text-xs"><span className={product.sale_price ? "text-muted-foreground line-through" : "font-semibold"}>{formatPrice(product.price)}</span>{product.sale_price && <strong className="text-foreground">{formatPrice(product.sale_price)}</strong>}</span>
                    </div>
                  </div>
                </button>;
              })}
            </div>
          )}
        </section>

        <section className="min-w-0">
          {!selected ? <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-border p-6 text-center"><span className="text-3xl">▦</span><h2 className="mt-3 font-semibold">یک محصول انتخاب کنید</h2><p className="mt-2 text-sm text-muted-foreground">یا محصول جدیدی بسازید تا رنگ‌ها و سایزهای آن را مدیریت کنید.</p></div> : (
            <div className="space-y-5">
              <section className="rounded-2xl border border-border bg-card p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><p className="text-xs text-muted-foreground">محصول انتخاب‌شده</p><h2 className="mt-1 text-xl font-bold">{selected.name}</h2><p className="mt-1 text-xs text-muted-foreground">کد محصول: {selected.product_code || "—"} · {formatPrice(selected.sale_price || selected.price)}</p></div>
                  <div className="flex flex-wrap gap-2"><button type="button" className={secondaryClass} onClick={() => resetProductForm(selected)}>ویرایش مشخصات</button><button type="button" disabled={saving} className={buttonClass} onClick={() => void saveWorkspace()}>{saving ? "در حال ذخیره…" : "ذخیره همه تغییرات"}</button><button type="button" disabled={saving} className={selected.is_active ? secondaryClass : buttonClass} onClick={() => void toggleProductPublication()}>{saving ? "در حال ذخیره…" : selected.is_active ? "خروج از فروشگاه" : "انتشار محصول"}</button></div>
                </div>
              </section>

              <ProductMeasurementManager
                productId={selected.id}
                sizes={sizes.filter((size) => editableSizeIds.has(size.id))}
                colors={selectedColors}
                variantSizes={variantSizes.filter((item) => selectedColors.some((color) => color.id === item.variant))}
              />

              <section className="rounded-2xl border border-border bg-card p-5">
                <h3 className="font-bold">رنگ‌های محصول</h3>
                <p className="mt-1 text-xs text-muted-foreground">برای هر رنگ یک کارت مستقل ساخته می‌شود؛ کد عددی کارت را سیستم خودکار اختصاص می‌دهد.</p>
                <form onSubmit={editingColorId ? saveWorkspace : addColor} className="mt-4 grid gap-3 sm:grid-cols-2">
                  <label className="text-sm">نام رنگ<input required value={colorName} onChange={(e) => setColorName(e.target.value)} className={inputClass} placeholder="مثلاً آبی آسمانی" /></label>
                  <label className="text-sm">کد رنگ<input type="color" value={hexColor} onChange={(e) => setHexColor(e.target.value)} className={inputClass + " h-11 p-1"} dir="ltr" /></label>
                  <div className="flex items-end gap-2"><button disabled={saving} className={buttonClass}>{editingColorId ? "ذخیره همه تغییرات" : "افزودن رنگ"}</button>{editingColorId && <button type="button" className={secondaryClass} onClick={() => { setEditingColorId(null); setColorName(""); setHexColor("#000000"); }}>لغو</button>}</div>
                </form>
                <div className="mt-4 space-y-2">
                  {selectedColors.map((color) => <div key={color.id} className="rounded-xl border border-border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <button type="button" onClick={() => setVariantId(color.id)} className="flex items-center gap-3 text-right"><span className="size-8 rounded-full border border-border" style={{ backgroundColor: color.hex_color || "#ddd" }} /><span><strong className="block text-sm">{color.name}</strong><span className="text-xs text-muted-foreground">کد کارت: {color.product_code}</span></span></button>
                      <div className="flex flex-wrap items-center gap-2">
                        <button type="button" aria-label={`انتقال رنگ ${color.name} به بالا`} disabled={saving || selectedColors[0]?.id === color.id} className={secondaryClass} onClick={() => void moveColor(color, -1)}>↑</button>
                        <button type="button" aria-label={`انتقال رنگ ${color.name} به پایین`} disabled={saving || selectedColors[selectedColors.length - 1]?.id === color.id} className={secondaryClass} onClick={() => void moveColor(color, 1)}>↓</button>
                        <button type="button" className={secondaryClass} onClick={() => { setEditingColorId(color.id); setColorName(color.name); setHexColor(color.hex_color || "#000000"); }}>ویرایش رنگ</button>
                        <button type="button" className={imageVariantId === color.id ? buttonClass : secondaryClass} onClick={() => setImageVariantId(imageVariantId === color.id ? null : color.id)}>{imageVariantId === color.id ? "بستن تصاویر" : "مدیریت تصاویر"}</button>
                        <button type="button" disabled={saving} className={secondaryClass} onClick={() => void toggleColor(color)}>{color.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}</button>
                        <button type="button" className={variantId === color.id ? buttonClass : secondaryClass} onClick={() => setVariantId(color.id)}>مدیریت سایزها</button>
                      </div>
                    </div>
                    {variantId === color.id && <div className="mt-4 border-t border-border pt-4">
                      <form onSubmit={addVariantSize} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_120px_auto]">
                        <label className="text-sm">سایز<select required value={sizeId} onChange={(e) => setSizeId(e.target.value)} className={inputClass}><option value="">انتخاب سایز</option>{sizes.filter((s) => categories.find((category) => category.id === selected.category)?.sizes.includes(s.id) && !variantSizes.some((vs) => vs.variant === color.id && vs.size === s.id) && !newVariantSizeDrafts.some((draft) => draft.variant === color.id && draft.size === s.id)).map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
                        <label className="text-sm">موجودی اولیه<input type="number" min="0" step="1" value={newVariantSizeStock} onChange={(e) => setNewVariantSizeStock(e.target.value)} className={inputClass} dir="ltr" /></label>
                        <div className="flex items-end"><button disabled={saving || !sizeId} className={buttonClass}>افزودن به پیش‌نویس</button></div>
                      </form>
                      <div className="mt-4 space-y-3">
                        {newVariantSizeDrafts.filter((draft) => draft.variant === color.id).map((draft) => <div key={draft.key} className="flex items-center justify-between rounded-lg border border-dashed border-primary/50 p-3 text-xs"><span>پیش‌نویس سایز: {sizes.find((item) => item.id === draft.size)?.label || "—"} · موجودی اولیه: {draft.initial_stock.toLocaleString("fa-IR")}</span><button type="button" className={secondaryClass} onClick={() => setNewVariantSizeDrafts((current) => current.filter((item) => item.key !== draft.key))}>حذف</button></div>)}
                        {variantSizes.filter((vs) => vs.variant === color.id).map((item) => {
                          const size = sizes.find((s) => s.id === item.size);
                          return <div key={item.id} className="rounded-xl bg-muted/50 p-3">
                            <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><strong>{size?.label || "سایز نامشخص"}{!item.is_active && <span className="mr-2 text-xs text-destructive">غیرفعال</span>}</strong><span className="flex items-center gap-3">موجودی: <b>{item.stock_quantity.toLocaleString("fa-IR")}</b><button type="button" disabled={saving} className={secondaryClass} onClick={() => void toggleVariantSize(item)}>{item.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}</button></span></div>
                            <div className="mt-3 flex flex-wrap items-end gap-2">
                              <label className="min-w-0 flex-1 text-xs">SKU<input required maxLength={64} value={skuDrafts[item.id] ?? item.sku} onChange={(e) => setSkuDrafts((old) => ({ ...old, [item.id]: e.target.value }))} className={inputClass} dir="ltr" /></label>
                              
                            </div>
                            <div className="mt-3 grid gap-2 sm:grid-cols-[110px_1fr]">
                              <label className="text-xs">تغییر تعداد<input required type="number" step="1" value={stockChanges[item.id] ?? ""} onChange={(e) => setStockChanges((old) => ({ ...old, [item.id]: e.target.value }))} className={inputClass} dir="ltr" placeholder="+10 / -2" /></label>
                              <label className="text-xs">دلیل تغییر<input required value={stockReasons[item.id] ?? ""} onChange={(e) => setStockReasons((old) => ({ ...old, [item.id]: e.target.value }))} className={inputClass} placeholder="مثلاً ورود بار جدید" /></label>
                              <p className="text-xs text-muted-foreground sm:col-span-2">تغییر موجودی همراه سایر تغییرات، با دکمه «ذخیره همه تغییرات» ثبت می‌شود.</p>
                            </div>
                            <InventoryHistory variantSizeId={item.id} />
                          </div>;
                        })}
                        {variantSizes.filter((vs) => vs.variant === color.id).length === 0 && <p className="text-xs text-muted-foreground">هنوز سایزی برای این رنگ ثبت نشده است.</p>}
                      </div>
                    </div>}
                    {imageVariantId === color.id && <VariantImageManager variantId={color.id} draftMode draft={imageDrafts[color.id]} onDraftChange={(draft) => setImageDrafts((old) => ({ ...old, [color.id]: draft }))} />}
                  </div>)}
                  {newColorDrafts.map((draft) => <div key={draft.key} className="rounded-xl border border-dashed border-primary/50 bg-muted/30 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-3"><span className="size-8 rounded-full border border-border" style={{ backgroundColor: draft.hex_color }} /><div><strong className="text-sm">{draft.name}</strong><p className="text-xs text-muted-foreground">پیش‌نویس رنگ جدید · کد کارت پس از ذخیره ساخته می‌شود</p></div></div>
                      <button type="button" className={secondaryClass} onClick={() => setNewColorDrafts((current) => current.filter((item) => item.key !== draft.key))}>حذف پیش‌نویس</button>
                    </div>
                    <div className="mt-3 flex flex-wrap items-end gap-2">
                      <label className="min-w-[150px] flex-1 text-xs">سایز<select value={newColorSizeSelections[draft.key] ?? ""} onChange={(event) => setNewColorSizeSelections((current) => ({ ...current, [draft.key]: event.target.value }))} className={inputClass}><option value="">انتخاب سایز</option>{sizes.filter((item) => categories.find((category) => category.id === selected.category)?.sizes.includes(item.id) && !draft.sizes.some((size) => size.size === item.id)).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
                      <label className="w-28 text-xs">موجودی اولیه<input type="number" min="0" step="1" value={newColorSizeStocks[draft.key] ?? "0"} onChange={(event) => setNewColorSizeStocks((current) => ({ ...current, [draft.key]: event.target.value }))} className={inputClass} dir="ltr" /></label>
                      <button type="button" disabled={!newColorSizeSelections[draft.key]} className={secondaryClass} onClick={() => addSizeToNewColor(draft.key)}>افزودن سایز</button>
                    </div>
                    {draft.sizes.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{draft.sizes.map((item) => <span key={item.size} className="rounded-lg border border-border bg-background px-2 py-1 text-xs">{sizes.find((size) => size.id === item.size)?.label} · موجودی {item.initial_stock.toLocaleString("fa-IR")} <button type="button" className="mr-1 text-destructive" onClick={() => setNewColorDrafts((current) => current.map((row) => row.key === draft.key ? { ...row, sizes: row.sizes.filter((size) => size.size !== item.size) } : row))}>×</button></span>)}</div>}
                  </div>)}
                  {selectedColors.length === 0 && <p className="rounded-xl bg-muted p-4 text-sm text-muted-foreground">هنوز رنگی برای این محصول ثبت نشده است.</p>}
                </div>
              </section>
            </div>
          )}
        </section>
      </div>}
      <p className="mt-7 text-xs leading-6 text-muted-foreground">تغییر موجودی فقط از مسیر ثبت گردش حسابرسی‌شده انجام می‌شود. تصاویر هر رنگ جداگانه مدیریت می‌شوند و اولین تصویر، تصویر اصلی کارت محصول است.</p>
    </main>
  );
}
