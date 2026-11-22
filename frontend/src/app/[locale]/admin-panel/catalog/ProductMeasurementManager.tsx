"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Size = { id: number; code: string; label: string; position: number };
type Color = { id: number; name: string };
type VariantSize = { id: number; variant: number; size: number; sku: string; stock_quantity: number };
type Page<T> = { results: T[]; next: string | null };
type Measurement = { id: number; product: number; size: number; name: string; value: string; unit: string; position: number };
type VariantMeasurement = { id: number; variant_size: number; name: string; value: string; unit: string; position: number };
type SizeDescription = { id: number; product: number; size: number; description: string };
type VariantSizeDescription = { id: number; variant_size: number; description: string };

const inputClass = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm";
const buttonClass = "rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondaryClass = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";

async function getAll<T>(path: string): Promise<T[]> {
  const rows: T[] = [];
  let next: string | null = path;
  let pages = 0;
  while (next && pages < 40) {
    const pageData: Page<T> = await apiRequest<Page<T>>("GET", next);
    rows.push(...pageData.results);
    next = pageData.next ? new URL(pageData.next, window.location.origin).pathname + new URL(pageData.next, window.location.origin).search : null;
    pages += 1;
  }
  return rows;
}

function errorText(error: unknown) {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "مجوز مشاهده یا ویرایش اندازه‌ها برای حساب مدیر فعال نیست.";
  if (error instanceof BrowserApiError && error.status === 400) return "اطلاعات اندازه معتبر نیست یا جایگاه آن تکراری است.";
  return "دریافت یا ذخیره اندازه‌ها انجام نشد.";
}

export default function ProductMeasurementManager({
  productId,
  sizes,
  colors,
  variantSizes,
}: {
  productId: number;
  sizes: Size[];
  colors: Color[];
  variantSizes: VariantSize[];
}) {
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [variantMeasurements, setVariantMeasurements] = useState<VariantMeasurement[]>([]);
  const [descriptions, setDescriptions] = useState<SizeDescription[]>([]);
  const [variantSizeDescriptions, setVariantSizeDescriptions] = useState<VariantSizeDescription[]>([]);
  const [canViewVariantDescriptions, setCanViewVariantDescriptions] = useState(false);
  const [sharedDrafts, setSharedDrafts] = useState<Record<number, { name: string; value: string; unit: string }>>({});
  const [newVariantName, setNewVariantName] = useState<Record<number, string>>({});
  const [newVariantValue, setNewVariantValue] = useState<Record<number, string>>({});
  const [newVariantUnit, setNewVariantUnit] = useState<Record<number, string>>({});
  const [descriptionDrafts, setDescriptionDrafts] = useState<Record<number, string>>({});
  const [variantDescriptionDrafts, setVariantDescriptionDrafts] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const variantSizeIdKey = variantSizes.map((item) => item.id).join(",");
  const loadData = useCallback(async () => {
    const [shared, specific, descriptionsData] = await Promise.all([
      getAll<Measurement>("/api/admin/catalog/product-measurements/"),
      getAll<VariantMeasurement>("/api/admin/catalog/variant-size-measurements/"),
      getAll<SizeDescription>("/api/admin/catalog/product-size-descriptions/"),
    ]);
    let variantDescriptionsData: VariantSizeDescription[] = [];
    let canViewSpecificDescriptions = true;
    try {
      variantDescriptionsData = await getAll<VariantSizeDescription>("/api/admin/catalog/variant-size-descriptions/");
    } catch (error) {
      if (!(error instanceof BrowserApiError) || (error.status !== 401 && error.status !== 403)) throw error;
      canViewSpecificDescriptions = false;
    }
    return { shared, specific, descriptionsData, variantDescriptionsData, canViewSpecificDescriptions };
  }, []);

  const applyData = useCallback(({ shared, specific, descriptionsData, variantDescriptionsData, canViewSpecificDescriptions }: Awaited<ReturnType<typeof loadData>>) => {
    setCanViewVariantDescriptions(canViewSpecificDescriptions);
    const allowedVariantSizeIds = new Set(variantSizeIdKey.split(",").filter(Boolean).map(Number));
    setMeasurements(shared.filter((item) => item.product === productId));
    setVariantMeasurements(specific.filter((item) => allowedVariantSizeIds.has(item.variant_size)));
    const productDescriptions = descriptionsData.filter((item) => item.product === productId);
    setDescriptions(productDescriptions);
    setDescriptionDrafts(Object.fromEntries(productDescriptions.map((item) => [item.size, item.description])));
    const specificDescriptions = variantDescriptionsData.filter((item) => allowedVariantSizeIds.has(item.variant_size));
    setVariantSizeDescriptions(specificDescriptions);
    setVariantDescriptionDrafts(Object.fromEntries(specificDescriptions.map((item) => [item.variant_size, item.description])));
  }, [productId, variantSizeIdKey]);

  const refresh = useCallback(async () => {
    applyData(await loadData());
  }, [applyData, loadData]);

  useEffect(() => {
    let active = true;
    void loadData().then((data) => {
      if (active) applyData(data);
    }).catch((e: unknown) => {
      if (active) setError(errorText(e));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [applyData, loadData]);

  const activeSizes = sizes;
  const labelForSize = (id: number) => sizes.find((size) => size.id === id)?.label ?? "سایز نامشخص";

  async function runSave(action: () => Promise<void>, success: string) {
    setSaving(true); setError(""); setNotice("");
    try {
      await action();
      await refresh();
      setNotice(success);
    } catch (e) { setError(errorText(e)); }
    finally { setSaving(false); }
  }

  async function addShared(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const size = Number((event.currentTarget.elements.namedItem("size") as HTMLInputElement).value);
    const draft = sharedDrafts[size];
    if (!draft?.name.trim() || !draft.value.trim()) return;
    const position = measurements.filter((item) => item.size === size).length;
    await runSave(async () => {
      await apiRequest("POST", "/api/admin/catalog/product-measurements/", {
        product: productId, size, name: draft.name.trim(), value: draft.value.trim(), unit: draft.unit.trim(), position,
      });
      setSharedDrafts((old) => ({ ...old, [size]: { name: "", value: "", unit: "سانتی‌متر" } }));
    }, "اندازه مشترک برای این سایز ثبت شد.");
  }

  async function saveShared(item: Measurement) {
    await runSave(async () => {
      await apiRequest("PATCH", `/api/admin/catalog/product-measurements/${item.id}/`, item);
    }, "اندازه مشترک ویرایش شد.");
  }

  async function saveDescription(sizeId: number) {
    const existing = descriptions.find((item) => item.size === sizeId);
    const description = descriptionDrafts[sizeId] ?? "";
    await runSave(async () => {
      if (existing) {
        await apiRequest("PATCH", `/api/admin/catalog/product-size-descriptions/${existing.id}/`, { description });
      } else if (description.trim()) {
        await apiRequest("POST", "/api/admin/catalog/product-size-descriptions/", { product: productId, size: sizeId, description });
      }
    }, "توضیحات سایز ذخیره شد.");
  }

  async function saveVariantDescription(variantSize: VariantSize) {
    const existing = variantSizeDescriptions.find((item) => item.variant_size === variantSize.id);
    const description = (variantDescriptionDrafts[variantSize.id] ?? "").trim();
    if (!description) return;
    await runSave(async () => {
      if (existing) {
        await apiRequest("PATCH", `/api/admin/catalog/variant-size-descriptions/${existing.id}/`, { description });
      } else {
        await apiRequest("POST", "/api/admin/catalog/variant-size-descriptions/", {
          variant_size: variantSize.id,
          description,
        });
      }
    }, "توضیحات اختصاصی این ترکیب رنگ و سایز ذخیره شد.");
  }

  async function addVariantMeasurement(event: FormEvent<HTMLFormElement>, variantSize: VariantSize) {
    event.preventDefault();
    const name = newVariantName[variantSize.id]?.trim() ?? "";
    const value = newVariantValue[variantSize.id]?.trim() ?? "";
    if (!name || !value) return;
    const position = variantMeasurements.filter((item) => item.variant_size === variantSize.id).length;
    await runSave(async () => {
      await apiRequest("POST", "/api/admin/catalog/variant-size-measurements/", {
        variant_size: variantSize.id, name, value, unit: (newVariantUnit[variantSize.id] ?? "سانتی‌متر").trim(), position,
      });
      setNewVariantName((old) => ({ ...old, [variantSize.id]: "" }));
      setNewVariantValue((old) => ({ ...old, [variantSize.id]: "" }));
    }, "اندازه اختصاصی این رنگ و سایز ثبت شد.");
  }

  async function saveVariantMeasurement(item: VariantMeasurement) {
    await runSave(async () => {
      await apiRequest("PATCH", `/api/admin/catalog/variant-size-measurements/${item.id}/`, item);
    }, "اندازه اختصاصی ویرایش شد.");
  }

  return <section className="rounded-2xl border border-border bg-card p-5">
    <div>
      <h3 className="font-bold">جدول اندازه‌گیری و مشخصات سایز</h3>
      <p className="mt-1 text-xs leading-6 text-muted-foreground">اندازه‌های مشترک برای همه رنگ‌های محصول استفاده می‌شوند. اگر برای یک ترکیب رنگ و سایز اندازه اختصاصی ثبت کنید، همان اطلاعات برای آن ترکیب اولویت خواهد داشت.</p>
    </div>
    {error && <p role="alert" className="mt-3 rounded-xl border border-destructive/40 p-3 text-sm">{error}</p>}
    {notice && <p role="status" className="mt-3 rounded-xl border border-border bg-muted p-3 text-sm">{notice}</p>}
    {loading ? <p className="py-6 text-sm text-muted-foreground">در حال دریافت اندازه‌ها…</p> : <>
      <div className="mt-4 grid gap-4">
        {activeSizes.map((size) => {
          const rows = measurements.filter((item) => item.size === size.id);
          return <div key={size.id} className="rounded-xl border border-border p-4">
            <h4 className="font-semibold">{size.label} <span className="text-xs font-normal text-muted-foreground">· اندازه مشترک همه رنگ‌ها</span></h4>
            <div className="mt-3 space-y-3">
              {rows.map((item) => <div key={item.id} className="grid gap-2 rounded-lg bg-muted/40 p-3 sm:grid-cols-[1fr_1fr_120px_auto]">
                <label className="text-xs">عنوان اندازه<input className={inputClass} value={item.name} onChange={(e) => setMeasurements((old) => old.map((row) => row.id === item.id ? { ...row, name: e.target.value } : row))} /></label>
                <label className="text-xs">مقدار<input className={inputClass} value={item.value} onChange={(e) => setMeasurements((old) => old.map((row) => row.id === item.id ? { ...row, value: e.target.value } : row))} /></label>
                <label className="text-xs">واحد<input className={inputClass} value={item.unit} onChange={(e) => setMeasurements((old) => old.map((row) => row.id === item.id ? { ...row, unit: e.target.value } : row))} /></label>
                <div className="flex items-end"><button type="button" disabled={saving} className={secondaryClass} onClick={() => void saveShared(item)}>ذخیره</button></div>
              </div>)}
              {rows.length === 0 && <p className="text-xs text-muted-foreground">هنوز اندازه مشترکی برای این سایز ثبت نشده است.</p>}
            </div>
            <div className="mt-4 border-t border-border pt-3">
              <form onSubmit={addShared} className="grid gap-2 sm:grid-cols-[1fr_1fr_120px_auto]">
                <input type="hidden" name="size" value={size.id} />
                <label className="text-xs">عنوان اندازه<input required className={inputClass} value={sharedDrafts[size.id]?.name ?? ""} onChange={(e) => setSharedDrafts((old) => ({ ...old, [size.id]: { name: e.target.value, value: old[size.id]?.value ?? "", unit: old[size.id]?.unit ?? "سانتی‌متر" } }))} placeholder="مثلاً دور سینه" /></label>
                <label className="text-xs">مقدار<input required className={inputClass} value={sharedDrafts[size.id]?.value ?? ""} onChange={(e) => setSharedDrafts((old) => ({ ...old, [size.id]: { name: old[size.id]?.name ?? "", value: e.target.value, unit: old[size.id]?.unit ?? "سانتی‌متر" } }))} placeholder="مثلاً ۹۶" /></label>
                <label className="text-xs">واحد<input className={inputClass} value={sharedDrafts[size.id]?.unit ?? "سانتی‌متر"} onChange={(e) => setSharedDrafts((old) => ({ ...old, [size.id]: { name: old[size.id]?.name ?? "", value: old[size.id]?.value ?? "", unit: e.target.value } }))} /></label>
                <div className="flex items-end"><button disabled={saving || !sharedDrafts[size.id]?.name.trim() || !sharedDrafts[size.id]?.value.trim()} className={buttonClass}>افزودن</button></div>
              </form>
            </div>
            <label className="mt-4 block text-xs">توضیحات این سایز<textarea rows={2} className={inputClass} value={descriptionDrafts[size.id] ?? ""} onChange={(e) => setDescriptionDrafts((old) => ({ ...old, [size.id]: e.target.value }))} placeholder="راهنمای اندازه یا توضیح تکمیلی…" /></label>
            <button type="button" disabled={saving} className={secondaryClass + " mt-2"} onClick={() => void saveDescription(size.id)}>ذخیره توضیحات سایز</button>
          </div>;
        })}
      </div>
      <div className="mt-5 border-t border-border pt-5">
        <h4 className="font-semibold">اندازه‌های اختصاصی هر رنگ و سایز</h4>
        <p className="mt-1 text-xs text-muted-foreground">برای مواردی که اندازه یک رنگ با جدول مشترک فرق دارد، مقدار اختصاصی ثبت کنید.</p>
        <div className="mt-3 space-y-3">
          {variantSizes.map((variantSize) => {
            const rows = variantMeasurements.filter((item) => item.variant_size === variantSize.id);
            return <div key={variantSize.id} className="rounded-xl border border-border p-3">
              <h5 className="text-sm font-semibold">{colors.find((color) => color.id === variantSize.variant)?.name ?? "رنگ"} · {labelForSize(variantSize.size)}</h5>
              <div className="mt-2 space-y-2">
                {rows.map((item) => <div key={item.id} className="grid gap-2 sm:grid-cols-[1fr_1fr_120px_auto]">
                  <input aria-label="عنوان اندازه اختصاصی" className={inputClass} value={item.name} onChange={(e) => setVariantMeasurements((old) => old.map((row) => row.id === item.id ? { ...row, name: e.target.value } : row))} />
                  <input aria-label="مقدار اندازه اختصاصی" className={inputClass} value={item.value} onChange={(e) => setVariantMeasurements((old) => old.map((row) => row.id === item.id ? { ...row, value: e.target.value } : row))} />
                  <input aria-label="واحد اندازه اختصاصی" className={inputClass} value={item.unit} onChange={(e) => setVariantMeasurements((old) => old.map((row) => row.id === item.id ? { ...row, unit: e.target.value } : row))} />
                  <button type="button" disabled={saving} className={secondaryClass} onClick={() => void saveVariantMeasurement(item)}>ذخیره</button>
                </div>)}
                <form onSubmit={(e) => void addVariantMeasurement(e, variantSize)} className="grid gap-2 sm:grid-cols-[1fr_1fr_120px_auto]">
                  <input className={inputClass} value={newVariantName[variantSize.id] ?? ""} onChange={(e) => setNewVariantName((old) => ({ ...old, [variantSize.id]: e.target.value }))} placeholder="عنوان اندازه اختصاصی" aria-label="عنوان اندازه جدید" required />
                  <input className={inputClass} value={newVariantValue[variantSize.id] ?? ""} onChange={(e) => setNewVariantValue((old) => ({ ...old, [variantSize.id]: e.target.value }))} placeholder="مقدار" aria-label="مقدار اندازه جدید" required />
                  <input className={inputClass} value={newVariantUnit[variantSize.id] ?? "سانتی‌متر"} onChange={(e) => setNewVariantUnit((old) => ({ ...old, [variantSize.id]: e.target.value }))} placeholder="واحد" aria-label="واحد اندازه جدید" />
                  <button disabled={saving} className={buttonClass}>افزودن</button>
                </form>
              </div>
              {canViewVariantDescriptions ? <>
                <label className="mt-3 block text-xs">توضیحات اختصاصی این ترکیب رنگ و سایز
                  <textarea rows={2} className={inputClass} value={variantDescriptionDrafts[variantSize.id] ?? ""} onChange={(e) => setVariantDescriptionDrafts((old) => ({ ...old, [variantSize.id]: e.target.value }))} placeholder="مثلاً تفاوت فیت یا اندازه در این رنگ و سایز…" />
                </label>
                <button type="button" disabled={saving || !(variantDescriptionDrafts[variantSize.id] ?? "").trim()} className={secondaryClass + " mt-2"} onClick={() => void saveVariantDescription(variantSize)}>ذخیره توضیحات ترکیب</button>
              </> : <p className="mt-3 text-xs text-muted-foreground">برای نمایش و مدیریت این توضیحات، مجوز مشاهده توضیحات اختصاصی ترکیب رنگ و سایز لازم است.</p>}
            </div>;
          })}
          {variantSizes.length === 0 && <p className="text-xs text-muted-foreground">ابتدا برای محصول رنگ و سایز تعریف کنید.</p>}
        </div>
      </div>
    </>}
  </section>;
}
