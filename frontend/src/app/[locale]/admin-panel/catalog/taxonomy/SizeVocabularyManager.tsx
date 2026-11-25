"use client";

import { useState, type FormEvent } from "react";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Size = { id: number; code: string; label: string; position: number };

const inputClass = "mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary";
const primaryClass = "rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50";
const secondaryClass = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";

function errorMessage(error: unknown) {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) {
    return "مجوز ساخت یا ویرایش سایز برای حساب مدیر فعال نیست.";
  }
  if (error instanceof BrowserApiError && error.status === 400) {
    return "نام سایز یا جایگاه نمایش معتبر نیست.";
  }
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "ذخیره سایز انجام نشد. اطلاعات را بررسی کنید.";
}

export default function SizeVocabularyManager({
  sizes,
  onSaved,
}: {
  sizes: Size[];
  onSaved: () => Promise<void>;
}) {
  const [label, setLabel] = useState("");
  const [position, setPosition] = useState(String(
    sizes.reduce((highest, size) => Math.max(highest, size.position), -1) + 1,
  ));
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function startEditing(size: Size) {
    setEditingId(size.id);
    setLabel(size.label);
    setPosition(String(size.position));
    setError("");
    setNotice("");
  }

  function resetForm() {
    setEditingId(null);
    setLabel("");
    setPosition(String(sizes.reduce((highest, size) => Math.max(highest, size.position), -1) + 1));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedLabel = label.trim();
    const normalizedPosition = Number(position);
    if (!normalizedLabel || normalizedLabel.length > 40) {
      setError("نام سایز باید بین ۱ تا ۴۰ نویسه باشد.");
      return;
    }
    if (!Number.isInteger(normalizedPosition) || normalizedPosition < 0) {
      setError("ترتیب نمایش باید عدد صحیح و صفر یا بیشتر باشد.");
      return;
    }
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const payload = { label: normalizedLabel, position: normalizedPosition };
      if (editingId === null) {
        await apiRequest<Size>("POST", "/api/admin/catalog/sizes/", payload);
        setNotice("سایز جدید ساخته شد؛ شناسه داخلی آن به‌صورت خودکار ایجاد شد.");
      } else {
        await apiRequest<Size>("PATCH", `/api/admin/catalog/sizes/${editingId}/`, payload);
        setNotice("مشخصات سایز ذخیره شد.");
      }
      resetForm();
      await onSaved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  const orderedSizes = [...sizes].sort((a, b) => a.position - b.position || a.id - b.id);

  return (
    <section className="rounded-2xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-bold">فهرست سایزهای فروشگاه</h2>
          <p className="mt-1 text-xs leading-6 text-muted-foreground">
            سایزها را یک‌بار تعریف کنید و بعد در دسته‌بندی‌های مرتبط فعالشان کنید. حذف فیزیکی نداریم تا سایزهای متصل به محصولات و سوابق سفارش‌ها آسیب نبینند.
          </p>
        </div>
        <span className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground">
          {sizes.length.toLocaleString("fa-IR")} سایز
        </span>
      </div>

      {error && <p role="alert" className="mt-3 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</p>}
      {notice && <p role="status" className="mt-3 rounded-xl border border-border bg-muted p-3 text-sm">{notice}</p>}

      <form onSubmit={save} className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_140px_auto]">
        <label className="text-sm">نام قابل نمایش سایز
          <input required maxLength={40} value={label} onChange={(event) => setLabel(event.target.value)} className={inputClass} placeholder="مثلاً XXL یا ۴۴" />
        </label>
        <label className="text-sm">ترتیب نمایش
          <input required type="number" min="0" step="1" value={position} onChange={(event) => setPosition(event.target.value)} className={inputClass} dir="ltr" />
        </label>
        <div className="flex items-end gap-2">
          <button type="submit" disabled={saving || !label.trim()} className={primaryClass}>
            {saving ? "در حال ذخیره…" : editingId === null ? "افزودن سایز" : "ذخیره سایز"}
          </button>
          {editingId !== null && <button type="button" disabled={saving} onClick={resetForm} className={secondaryClass}>لغو</button>}
        </div>
      </form>

      <div className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {orderedSizes.map((size) => (
          <article key={size.id} className="flex items-center justify-between gap-3 rounded-xl border border-border p-3">
            <div className="min-w-0">
              <strong className="block text-sm">{size.label}</strong>
              <span className="mt-1 block text-xs text-muted-foreground">ترتیب: {size.position.toLocaleString("fa-IR")}</span>
            </div>
            <button type="button" disabled={saving} onClick={() => startEditing(size)} className={secondaryClass}>ویرایش</button>
          </article>
        ))}
        {orderedSizes.length === 0 && <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">هنوز سایزی تعریف نشده است.</p>}
      </div>
    </section>
  );
}
