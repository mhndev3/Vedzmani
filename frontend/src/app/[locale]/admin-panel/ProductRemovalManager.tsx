"use client";

import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/browser-api";

type Product = { id: number; name: string; product_code: string | null; is_active: boolean };
type Page<T> = { results: T[]; next: string | null };

async function getAllProducts(): Promise<Product[]> {
  const rows: Product[] = [];
  let next: string | null = "/api/admin/catalog/products/";
  const visited = new Set<string>();
  while (next) {
    if (visited.has(next) || visited.size >= 1000) throw new Error("صفحه‌بندی محصولات معتبر نیست.");
    visited.add(next);
    const pageData: Page<Product> = await apiRequest<Page<Product>>("GET", next);
    rows.push(...pageData.results);
    next = pageData.next ? new URL(pageData.next, window.location.origin).pathname + new URL(pageData.next, window.location.origin).search : null;
  }
  return rows;
}

export default function ProductRemovalManager() {
  const [products, setProducts] = useState<Product[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    void getAllProducts().then((rows) => {
      if (active) setProducts(rows);
    }).catch(() => {
      if (active) setError("دریافت فهرست محصولات انجام نشد. مجوز مشاهده محصولات را بررسی کنید.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  const visible = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    return products.filter((product) =>
      !term || product.name.toLocaleLowerCase().includes(term) || String(product.product_code ?? "").includes(term)
    );
  }, [products, search]);
  const activeCount = products.filter((product) => product.is_active).length;

  async function changeVisibility(product: Product) {
    const nextActive = !product.is_active;
    const accepted = window.confirm(
      nextActive
        ? "محصول «" + product.name + "» دوباره در فروشگاه منتشر شود؟"
        : "محصول «" + product.name + "» از فروشگاه خارج شود؟ اطلاعات، رنگ‌ها، موجودی و سوابق آن برای حفظ تاریخچه باقی می‌مانند."
    );
    if (!accepted) return;
    setSavingId(product.id);
    setError("");
    setNotice("");
    try {
      await apiRequest<Product>("PATCH", "/api/admin/catalog/products/" + product.id + "/", { is_active: nextActive });
      setProducts((current) => current.map((item) => item.id === product.id ? { ...item, is_active: nextActive } : item));
      setNotice(nextActive ? "محصول «" + product.name + "» دوباره در فروشگاه منتشر شد." : "محصول «" + product.name + "» از فروشگاه حذف شد؛ سوابق آن حفظ شده‌اند.");
    } catch {
      setError("حذف محصول انجام نشد. دسترسی تغییر محصول را بررسی کنید.");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <section className="mt-4 rounded-2xl border border-border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-bold">حذف محصول از فروشگاه</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            این بخش فقط در صفحه اصلی پنل قرار دارد. محصول از ویترین پنهان می‌شود، اما اطلاعات، موجودی و سوابق آن پاک نمی‌شوند.
          </p>
        </div>
        <span className="rounded-full bg-muted px-3 py-1 text-xs">{activeCount.toLocaleString("fa-IR")} محصول فعال</span>
      </div>
      {notice && <p role="status" className="mt-3 rounded-lg bg-muted p-3 text-sm">{notice}</p>}
      {error && <p role="alert" className="mt-3 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      <input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="جستجوی محصول برای حذف…"
        aria-label="جستجوی محصول برای حذف"
        className="mt-4 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm"
      />
      {loading ? <p className="py-6 text-center text-sm text-muted-foreground">در حال دریافت محصولات…</p> :
        visible.length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">محصولی برای نمایش پیدا نشد.</p> :
          <div className="mt-3 max-h-80 space-y-2 overflow-y-auto">
            {visible.map((product) => (
              <div key={product.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border p-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold">{product.name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">کد محصول: {product.product_code || "—"} · {product.is_active ? "در فروشگاه" : "خارج از فروشگاه"}</p>
                </div>
                <button
                  type="button"
                  disabled={savingId !== null}
                  onClick={() => void changeVisibility(product)}
                  className="rounded-lg border border-destructive/40 px-3 py-2 text-xs font-semibold text-destructive hover:bg-destructive/5 disabled:opacity-50"
                >
                  {savingId === product.id ? "در حال ذخیره…" : product.is_active ? "حذف از فروشگاه" : "بازگردانی به فروشگاه"}
                </button>
              </div>
            ))}
          </div>}
    </section>
  );
}
