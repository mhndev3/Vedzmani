"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import Image from "next/image";
import { apiRequest, apiMultipartRequest, BrowserApiError } from "@/lib/browser-api";
import SizeVocabularyManager from "./SizeVocabularyManager";

type CatalogGroup = "categories" | "collections";
type ProductField = { key: string; label: string; type: "text" | "number"; unit: string; required: boolean };
type Entry = { id: number; name: string; slug: string; is_active: boolean; position: number; image_url?: string | null; product_fields?: ProductField[]; sizes?: number[]; is_homepage_featured?: boolean; homepage_position?: number };
type Size = { id: number; code: string; label: string; position: number };
type Page<T> = { results: T[]; next: string | null };

const inputClass = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary";
const primaryClass = "rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondaryClass = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";

async function getAll<T>(path: string): Promise<T[]> {
  const rows: T[] = [];
  let next: string | null = path;
  let pages = 0;
  while (next && pages < 40) {
    const pageData: Page<T> = await apiRequest<Page<T>>("GET", next);
    rows.push(...pageData.results);
    next = pageData.next
      ? new URL(pageData.next, window.location.origin).pathname + new URL(pageData.next, window.location.origin).search
      : null;
    pages += 1;
  }
  return rows;
}

function errorMessage(error: unknown): string {
  if (error instanceof BrowserApiError) {
    if (error.status === 401 || error.status === 403) return "دسترسی کافی ندارید؛ مجوزهای مشاهده و ویرایش مدل را بررسی کنید.";
    if (error.status === 400) return "نام یا شناسه واردشده معتبر نیست یا قبلاً استفاده شده است.";
    if (error.status === 0) return "ارتباط با سرور برقرار نشد.";
  }
  return "ذخیره اطلاعات انجام نشد. ورودی‌ها را بررسی و دوباره تلاش کنید.";
}

export default function AdminTaxonomyPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [group, setGroup] = useState<CatalogGroup>("categories");
  const [categories, setCategories] = useState<Entry[]>([]);
  const [collections, setCollections] = useState<Entry[]>([]);
  const [sizes, setSizes] = useState<Size[]>([]);
  const [selectedSizeIds, setSelectedSizeIds] = useState<number[]>([]);
  const [categoryPlacement, setCategoryPlacement] = useState<"catalog" | "homepage">("catalog");
  const [homepagePosition, setHomepagePosition] = useState("6");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [removeImage, setRemoveImage] = useState(false);
  const [productFields, setProductFields] = useState<ProductField[]>([]);
  const previewObjectUrl = useRef<string | null>(null);

  const endpoint = group === "categories" ? "/api/admin/catalog/categories/" : "/api/admin/catalog/collections/";
  const entries = group === "categories" ? categories : collections;

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [categoryRows, collectionRows, sizeRows] = await Promise.all([
        getAll<Entry>("/api/admin/catalog/categories/"),
        getAll<Entry>("/api/admin/catalog/collections/"),
        getAll<Size>("/api/admin/catalog/sizes/"),
      ]);
      setCategories(categoryRows);
      setCollections(collectionRows);
      setSizes(sizeRows);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [categoryRows, collectionRows, sizeRows] = await Promise.all([
          getAll<Entry>("/api/admin/catalog/categories/"),
          getAll<Entry>("/api/admin/catalog/collections/"),
          getAll<Size>("/api/admin/catalog/sizes/"),
        ]);
        if (!cancelled) {
          setCategories(categoryRows);
          setCollections(collectionRows);
          setSizes(sizeRows);
          const query = new URLSearchParams(window.location.search);
          const editId = Number(query.get("edit"));
          const selectedCategory = Number.isSafeInteger(editId) && editId > 0
            ? categoryRows.find((entry) => entry.id === editId)
            : undefined;
          if (selectedCategory) {
            resetForm(selectedCategory);
            setNotice("دسته‌بندی انتخاب‌شده برای ویرایش باز شد.");
          } else if (query.get("new") === "1") {
            resetForm();
            setNotice("فرم ایجاد دسته‌بندی جدید آماده است.");
          }
        }
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  const visibleEntries = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    return [...entries]
      .sort((a, b) => a.position - b.position || a.id - b.id)
      .filter((entry) => !term || entry.name.toLocaleLowerCase().includes(term) || entry.slug.toLocaleLowerCase().includes(term));
  }, [entries, search]);

  function resetForm(entry?: Entry, targetGroup: CatalogGroup = group) {
    if (previewObjectUrl.current) URL.revokeObjectURL(previewObjectUrl.current);
    previewObjectUrl.current = null;
    setEditing(entry?.id ?? null);
    setName(entry?.name ?? "");
    setSlug(entry?.slug ?? "");
    setImageFile(null);
    setImagePreview(targetGroup === "categories" ? entry?.image_url ?? null : null);
    setRemoveImage(false);
    setProductFields(targetGroup === "categories" ? entry?.product_fields ?? [] : []);
    setSelectedSizeIds(targetGroup === "categories" ? entry?.sizes ?? [] : []);
    setCategoryPlacement(entry?.is_homepage_featured ? "homepage" : "catalog");
    setHomepagePosition(String((entry?.homepage_position ?? 5) + 1));
    setError("");
    setNotice("");
  }

  function addProductField() {
    const nextNumber = productFields.reduce((max, field) => {
      const match = /^attribute_(\d+)$/.exec(field.key);
      return match ? Math.max(max, Number(match[1])) : max;
    }, 0) + 1;
    setProductFields(current => [...current, {
      key: `attribute_${nextNumber}`,
      label: "",
      type: "text",
      unit: "",
      required: false,
    }]);
  }

  function updateProductField(index: number, patch: Partial<ProductField>) {
    setProductFields(current => current.map((field, fieldIndex) =>
      fieldIndex === index ? { ...field, ...patch } : field
    ));
  }

  function removeProductField(index: number) {
    setProductFields(current => current.filter((_, fieldIndex) => fieldIndex !== index));
  }

    function chooseCategoryImage(file: File | null) {
    if (previewObjectUrl.current) URL.revokeObjectURL(previewObjectUrl.current);
    previewObjectUrl.current = file ? URL.createObjectURL(file) : null;
    setImageFile(file);
    setImagePreview(file ? previewObjectUrl.current : null);
    setRemoveImage(false);
  }

  useEffect(() => () => {
    if (previewObjectUrl.current) URL.revokeObjectURL(previewObjectUrl.current);
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const payload = {
        name: name.trim(),
        slug: slug.trim(),
        position: editing === null ? entries.length : entries.find((entry) => entry.id === editing)?.position ?? 0,
        ...(group === "categories" ? {
          product_fields: productFields,
          size_ids: selectedSizeIds,
          is_homepage_featured: categoryPlacement === "homepage",
          homepage_position: Math.max(0, Number(homepagePosition) - 1),
        } : {}),
      };
      const method = editing === null ? "POST" : "PATCH";
      const url = editing === null ? endpoint : endpoint + editing + "/";
      if (group === "categories" && (imageFile || removeImage)) {
        const form = new FormData();
        Object.entries({ ...payload, ...(editing === null ? { is_active: true } : {}) }).forEach(([key, value]) => {
          form.set(key, key === "product_fields" || key === "size_ids" ? JSON.stringify(value) : String(value));
        });
        if (imageFile) form.set("image", imageFile);
        if (removeImage) form.set("remove_image", "true");
        await apiMultipartRequest<Entry>(method, url, form);
      } else if (editing === null) {
        await apiRequest<Entry>("POST", endpoint, { ...payload, is_active: true });
      } else {
        await apiRequest<Entry>("PATCH", endpoint + editing + "/", payload);
      }
      setNotice(group === "categories" ? (editing === null ? "دسته‌بندی جدید ساخته شد." : "تغییرات دسته‌بندی ذخیره شد.") : (editing === null ? "مجموعه جدید ساخته شد." : "تغییرات مجموعه ذخیره شد."));
      resetForm();
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(entry: Entry) {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await apiRequest<Entry>("PATCH", endpoint + entry.id + "/", { is_active: !entry.is_active });
      setNotice(entry.is_active ? "مورد انتخاب‌شده غیرفعال شد؛ سابقه و محصولات مرتبط حفظ شدند." : "مورد دوباره فعال شد.");
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function move(entry: Entry, delta: number) {
    const ordered = [...entries].sort((a, b) => a.position - b.position || a.id - b.id);
    const index = ordered.findIndex((item) => item.id === entry.id);
    const target = index + delta;
    if (target < 0 || target >= ordered.length) return;
    const reordered = [...ordered];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await apiRequest<Entry[]>("POST", endpoint + "reorder/", {
        entry_ids: reordered.map((item) => item.id),
      });
      setNotice("ترتیب نمایش به‌صورت یکپارچه ذخیره شد.");
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
      await refresh();
    } finally {
      setSaving(false);
    }
  }

  return (
    <main dir="rtl" className="mx-auto w-full max-w-6xl px-4 py-8 sm:py-10">
      <div className="mb-7">
        <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
        <h1 className="mt-3 text-2xl font-bold sm:text-3xl">مدیریت دسته‌بندی‌ها، مجموعه‌ها و سایزها</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">ساختار کاتالوگ را مدیریت کنید. غیرفعال‌سازی به‌جای حذف انجام می‌شود تا ارتباط محصولات و سوابق حفظ شود.</p>
      </div>

      <div className="mb-5 flex flex-wrap gap-2" role="tablist" aria-label="نوع گروه کاتالوگ">
        <button type="button" role="tab" aria-selected={group === "categories"} className={group === "categories" ? primaryClass : secondaryClass} onClick={() => { setGroup("categories"); resetForm(undefined, "categories"); setSearch(""); }}>دسته‌بندی‌ها</button>
        <button type="button" role="tab" aria-selected={group === "collections"} className={group === "collections" ? primaryClass : secondaryClass} onClick={() => { setGroup("collections"); resetForm(undefined, "collections"); setSearch(""); }}>مجموعه‌ها</button>
      </div>

      {notice && <p role="status" className="mb-4 rounded-xl border border-border bg-muted p-3 text-sm">{notice}</p>}
      {error && <p role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.4fr)]">
        <section className="rounded-2xl border border-border bg-card p-5">
          <h2 className="font-bold">{editing === null ? "افزودن مورد جدید" : "ویرایش مورد"}</h2>
          <form onSubmit={save} className="mt-4 space-y-4">
            <label className="block text-sm">نام فارسی
              <input required maxLength={100} value={name} onChange={(event) => setName(event.target.value)} className={inputClass} />
            </label>
            <label className="block text-sm">شناسه انگلیسی (Slug)
              <input required maxLength={120} pattern="[A-Za-z0-9_-]+" dir="ltr" value={slug} onChange={(event) => setSlug(event.target.value)} className={inputClass} />
            </label>
            {group === "categories" && (
              <div className="space-y-3">
              <section className="space-y-3 rounded-xl border border-border p-3">
                <div>
                  <h3 className="text-sm font-semibold">محل نمایش دسته‌بندی</h3>
                  <p className="mt-1 text-xs text-muted-foreground">دسته‌بندی فروشگاه برای ساختار محصولات است؛ گزینه صفحه اصلی آن را به کارت‌های فعلی صفحه اصلی اضافه می‌کند و چیزی را جایگزین نمی‌کند.</p>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className="flex items-center gap-2 rounded-lg border border-border p-3 text-sm"><input type="radio" name="category-placement" checked={categoryPlacement === "catalog"} onChange={() => setCategoryPlacement("catalog")} />دسته‌بندی اصلی فروشگاه</label>
                  <label className="flex items-center gap-2 rounded-lg border border-border p-3 text-sm"><input type="radio" name="category-placement" checked={categoryPlacement === "homepage"} onChange={() => setCategoryPlacement("homepage")} />دسته‌بندی صفحه اصلی</label>
                </div>
                {categoryPlacement === "homepage" && <label className="block text-sm">جایگاه در صفحه اصلی (۱ یعنی اولین کارت)<input required type="number" min="1" max="100" value={homepagePosition} onChange={event => setHomepagePosition(event.target.value)} className={inputClass} dir="ltr" /><span className="mt-1 block text-xs text-muted-foreground">پنج دسته فعلی حفظ می‌شوند؛ جایگاه این مورد را برای افزودن آن به فهرست تعیین کنید.</span></label>}
              </section>
              <section className="space-y-3 rounded-xl border border-border p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold">سایزهای مجاز این دسته‌بندی</h3>
                    <p className="mt-1 text-xs text-muted-foreground">فقط سایزهای انتخاب‌شده هنگام ساخت محصول در این دسته‌بندی نمایش داده می‌شوند.</p>
                  </div>
                  <Link href="#size-vocabulary" className="text-xs font-medium text-primary underline underline-offset-4">مدیریت فهرست سایزها</Link>
                </div>
                {sizes.length === 0 ? <p className="text-xs text-muted-foreground">ابتدا از فهرست سایزها گزینه تعریف کنید.</p> : (
                  <div className="flex flex-wrap gap-2">
                    {sizes.map((size) => <label key={size.id} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm">
                      <input type="checkbox" checked={selectedSizeIds.includes(size.id)} onChange={(event) => setSelectedSizeIds((current) => event.target.checked ? [...current, size.id] : current.filter((id) => id !== size.id))} />
                      {size.label} <span dir="ltr" className="text-xs text-muted-foreground">({size.code})</span>
                    </label>)}
                  </div>
                )}
              </section>
              <section className="space-y-3 rounded-xl border border-border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold">فیلدهای اختصاصی فرم محصول</h3>
                    <p className="mt-1 text-xs text-muted-foreground">فقط همین فیلدها هنگام انتخاب این دسته‌بندی در فرم محصول نمایش داده می‌شوند.</p>
                  </div>
                  <button type="button" className={secondaryClass} disabled={saving || productFields.length >= 20} onClick={addProductField}>＋ افزودن فیلد</button>
                </div>
                {productFields.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">برای این دسته‌بندی فیلد اختصاصی تعریف نشده است.</p>
                ) : (
                  <div className="space-y-2">
                    {productFields.map((field, index) => (
                      <div key={field.key} className="grid gap-2 rounded-lg bg-muted/30 p-3 sm:grid-cols-[minmax(0,1.3fr)_minmax(100px,0.7fr)_minmax(90px,0.6fr)_auto]">
                        <label className="text-xs">عنوان فیلد
                          <input required maxLength={80} value={field.label} onChange={(event) => updateProductField(index, { label: event.target.value })} className={inputClass} placeholder="مثلاً جنس پارچه" />
                          <span dir="ltr" className="mt-1 block text-[10px] text-muted-foreground">{field.key}</span>
                        </label>
                        <label className="text-xs">نوع مقدار
                          <select value={field.type} onChange={(event) => updateProductField(index, { type: event.target.value as ProductField["type"] })} className={inputClass}>
                            <option value="text">متنی</option>
                            <option value="number">عددی</option>
                          </select>
                        </label>
                        <label className="text-xs">واحد (اختیاری)
                          <input maxLength={24} value={field.unit} onChange={(event) => updateProductField(index, { unit: event.target.value })} className={inputClass} placeholder="مثلاً سانتی‌متر" />
                        </label>
                        <div className="flex flex-wrap items-end gap-2">
                          <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={field.required} onChange={(event) => updateProductField(index, { required: event.target.checked })} />اجباری</label>
                          <button type="button" className={secondaryClass} disabled={saving} onClick={() => removeProductField(index)}>حذف</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
              <div className="space-y-2">
                <label className="block text-sm">تصویر دسته‌بندی (اختیاری)
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={saving}
                    onChange={(event) => {
                      const file = event.target.files?.[0] ?? null;
                      if (file && file.size > 8 * 1024 * 1024) {
                        setError("حجم تصویر نباید بیشتر از ۸ مگابایت باشد.");
                        event.currentTarget.value = "";
                        return;
                      }
                      chooseCategoryImage(file);
                    }}
                    className={inputClass}
                  />
                </label>
                {imagePreview && (
                  <div className="flex items-center gap-3 rounded-xl border border-border p-3">
                    <Image src={imagePreview} alt={name || "پیش‌نمایش تصویر دسته‌بندی"} width={88} height={88} unoptimized className="size-22 rounded-lg object-cover" />
                    <div className="min-w-0 flex-1 text-xs text-muted-foreground">
                      <p className="font-medium text-foreground">{imageFile ? imageFile.name : "تصویر فعلی دسته‌بندی"}</p>
                      <p className="mt-1">تصویر در کارت دسته‌بندی صفحه اصلی نمایش داده می‌شود.</p>
                    </div>
                    {editing !== null && !imageFile && <button type="button" className={secondaryClass} disabled={saving} onClick={() => { setImagePreview(null); setRemoveImage(true); }}>حذف تصویر</button>}
                    {imageFile && <button type="button" className={secondaryClass} disabled={saving} onClick={() => chooseCategoryImage(null)}>لغو انتخاب</button>}
                  </div>
                )}
              </div>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <button type="submit" disabled={saving || !name.trim() || !slug.trim()} className={primaryClass}>{saving ? "در حال ذخیره…" : editing === null ? "ایجاد" : "ذخیره تغییرات"}</button>
              {editing !== null && <button type="button" disabled={saving} className={secondaryClass} onClick={() => resetForm()}>انصراف</button>}
            </div>
          </form>
          <p className="mt-5 text-xs leading-6 text-muted-foreground">شناسه انگلیسی باید یکتا باشد و در نشانی‌ها استفاده می‌شود. حذف فیزیکی در این بخش وجود ندارد.</p>
        </section>

        <section className="min-w-0 rounded-2xl border border-border bg-card p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-bold">{group === "categories" ? "فهرست دسته‌بندی‌ها" : "فهرست مجموعه‌ها"}</h2>
            <span className="text-xs text-muted-foreground">{entries.length.toLocaleString("fa-IR")} مورد</span>
          </div>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="جستجو با نام یا شناسه…" className={inputClass + " my-4"} />
          {loading ? <p className="py-8 text-center text-sm text-muted-foreground">در حال دریافت اطلاعات…</p> :
            visibleEntries.length === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">موردی پیدا نشد.</p> :
              <div className="divide-y divide-border">
                {visibleEntries.map((entry) => {
                  const index = entries.slice().sort((a, b) => a.position - b.position || a.id - b.id).findIndex((item) => item.id === entry.id);
                  return (
                    <article key={entry.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                      <div className="flex min-w-0 items-center gap-3">
                        {group === "categories" && (
                          entry.image_url
                            ? <Image src={entry.image_url} alt="" width={56} height={56} unoptimized className="size-14 shrink-0 rounded-xl border border-border object-cover" />
                            : <div className="flex size-14 shrink-0 items-center justify-center rounded-xl border border-dashed border-border text-xs text-muted-foreground">بدون تصویر</div>
                        )}
                        <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-semibold">{entry.name}</h3>
                          <span className={entry.is_active ? "rounded-full bg-muted px-2 py-1 text-[10px]" : "rounded-full border border-border px-2 py-1 text-[10px] text-muted-foreground"}>{entry.is_active ? "فعال" : "غیرفعال"}</span>
                          {group === "categories" && <span className="rounded-full border border-border px-2 py-1 text-[10px]">{entry.is_homepage_featured ? "صفحه اصلی · " + (Number(entry.homepage_position ?? 0) + 1) : "فروشگاه"}</span>}
                        </div>
                        <p dir="ltr" className="mt-1 text-left text-xs text-muted-foreground">{entry.slug} · {entry.position}</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        <button type="button" className={secondaryClass} disabled={saving || index === 0} onClick={() => void move(entry, -1)} aria-label="انتقال به بالا">↑</button>
                        <button type="button" className={secondaryClass} disabled={saving || index === entries.length - 1} onClick={() => void move(entry, 1)} aria-label="انتقال به پایین">↓</button>
                        <button type="button" className={secondaryClass} disabled={saving} onClick={() => resetForm(entry)}>ویرایش</button>
                        <button type="button" className={secondaryClass} disabled={saving} onClick={() => void toggleActive(entry)}>{entry.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}</button>
                      </div>
                    </article>
                  );
                })}
              </div>}
        </section>
      </div>

      <div id="size-vocabulary" className="mt-6 scroll-mt-6">
        <SizeVocabularyManager sizes={sizes} onSaved={async () => { await refresh(); }} />
      </div>
    </main>
  );
}
