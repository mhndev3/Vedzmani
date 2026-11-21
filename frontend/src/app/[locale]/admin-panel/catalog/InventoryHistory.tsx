"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Adjustment = {
  id: number;
  variant_size: number;
  quantity_change: number;
  stock_after: number;
  reason: string;
  created_by: number | null;
  created_by_label: string;
  created_at: string;
};
type Page = { results: Adjustment[]; next: string | null; count: number };

const dateFormatter = new Intl.DateTimeFormat("fa-IR", {
  dateStyle: "medium",
  timeStyle: "short",
});

function message(error: unknown): string {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) {
    return "برای مشاهده سوابق موجودی، مجوز مشاهده گردش انبار لازم است.";
  }
  return "دریافت سوابق موجودی انجام نشد. اتصال سرور را بررسی کنید.";
}

export default function InventoryHistory({ variantSizeId }: { variantSizeId: number }) {
  const [rows, setRows] = useState<Adjustment[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (url: string, append: boolean) => {
    if (append) setLoadingMore(true);
    else setLoading(true);
    setError("");
    try {
      const page = await apiRequest<Page>("GET", url);
      setRows((current) => append ? [...current, ...page.results] : page.results);
      setNext(page.next);
      setCount(page.count);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    void load(`/api/admin/inventory/adjustments/?variant_size=${variantSizeId}`, false);
  }, [variantSizeId, load]);

  return (
    <section className="mt-3 rounded-xl border border-border bg-background p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold">سوابق گردش موجودی</h4>
        <span className="text-xs text-muted-foreground">{count.toLocaleString("fa-IR")} ثبت</span>
      </div>
      {loading ? <p className="py-3 text-center text-xs text-muted-foreground">در حال دریافت سوابق…</p> :
        error ? <p role="alert" className="py-3 text-xs text-destructive">{error}</p> :
        rows.length === 0 ? <p className="py-3 text-xs text-muted-foreground">برای این سایز هنوز گردش موجودی ثبت نشده است.</p> : (
          <div className="space-y-2">
            {rows.map((row) => (
              <article key={row.id} className="rounded-lg border border-border p-3 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <strong className={row.quantity_change > 0 ? "text-emerald-700" : "text-destructive"}>
                    {row.quantity_change > 0 ? "+" : ""}{row.quantity_change.toLocaleString("fa-IR")} عدد
                  </strong>
                  <span className="text-muted-foreground">{dateFormatter.format(new Date(row.created_at))}</span>
                </div>
                <p className="mt-2">{row.reason}</p>
                <div className="mt-2 flex flex-wrap justify-between gap-2 text-muted-foreground">
                  <span>موجودی پس از تغییر: {row.stock_after.toLocaleString("fa-IR")}</span>
                  <span>ثبت‌کننده: {row.created_by_label || "نامشخص"}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      {next && !error && (
        <button type="button" disabled={loadingMore} onClick={() => {
          const parsed = new URL(next, window.location.origin);
          void load(parsed.pathname + parsed.search, true);
        }} className="mt-3 w-full rounded-lg border border-border px-3 py-2 text-xs hover:bg-muted disabled:opacity-50">
          {loadingMore ? "در حال دریافت…" : "نمایش سوابق قدیمی‌تر"}
        </button>
      )}
    </section>
  );
}
