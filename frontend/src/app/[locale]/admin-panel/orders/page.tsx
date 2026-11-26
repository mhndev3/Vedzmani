"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type OrderItem = {
  id: number;
  variant_size_id: number;
  product_name: string;
  color_name: string;
  size_label: string;
  sku: string;
  unit_price: string;
  quantity: number;
  subtotal: string;
};
type Order = {
  id: number;
  status: string;
  payment_status: string;
  customer_phone: string;
  customer_account_id: number;
  recipient_name: string;
  province: string;
  city: string;
  address: string;
  postal_code: string;
  pii_hidden: boolean;
  total: string;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
};
type Page = { count: number; next: string | null; previous: string | null; results: Order[] };

const inputClass = "rounded-xl border border-border bg-background px-3 py-2.5 text-sm";
const buttonClass = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";
const dateFormat = new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short" });
const money = (value: string) => Number(value).toLocaleString("fa-IR") + " تومان";
const orderStatus: Record<string, string> = { pending: "در انتظار بررسی", confirmed: "تأییدشده" };
const paymentStatus: Record<string, string> = { unpaid: "پرداخت‌نشده", paid: "پرداخت‌شده", failed: "ناموفق" };

function errorText(error: unknown) {
  if (error instanceof BrowserApiError && error.status === 403) return "مجوز مشاهده سفارش‌ها برای حساب شما فعال نیست.";
  if (error instanceof BrowserApiError && error.status === 401) return "نشست ورود منقضی شده است. دوباره وارد حساب مدیریت شوید.";
  return "دریافت اطلاعات سفارش‌ها با خطا مواجه شد.";
}

export default function AdminOrdersPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [rows, setRows] = useState<Order[]>([]);
  const [selected, setSelected] = useState<Order | null>(null);
  const [count, setCount] = useState(0);
  const [next, setNext] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [payment, setPayment] = useState("");
  const initialQueryApplied = useRef(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (url?: string, paymentOverride?: string) => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams();
      if (search.trim()) query.set("search", search.trim());
      if (status) query.set("status", status);
      if (paymentOverride) query.set("payment_status", paymentOverride);
      else if (payment) query.set("payment_status", payment);
      const target = url ?? "/api/admin/orders/?" + query.toString();
      const data = await apiRequest<Page>("GET", target);
      setRows(data.results);
      setCount(data.count);
      setNext(data.next);
      setSelected((current) => current ? data.results.find((row) => row.id === current.id) ?? null : null);
    } catch (cause) {
      setError(errorText(cause));
      setRows([]);
      setCount(0);
      setNext(null);
    } finally {
      setLoading(false);
    }
  }, [payment, search, status]);

  useEffect(() => {
    if (!initialQueryApplied.current) {
      initialQueryApplied.current = true;
      const requestedPayment = new URLSearchParams(window.location.search).get("payment_status");
      void Promise.resolve().then(() => load(undefined, requestedPayment === "paid" ? "paid" : undefined));
      return;
    }
    void Promise.resolve().then(() => load());
  }, [load]);

  async function openOrder(order: Order) {
    setSelected(order);
    try {
      const detail = await apiRequest<Order>("GET", `/api/admin/orders/${order.id}/`);
      setSelected(detail);
    } catch (cause) {
      setError(errorText(cause));
    }
  }

  return (
    <main dir="rtl" className="mx-auto w-full max-w-7xl px-4 py-8 sm:py-10">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
          <h1 className="mt-3 text-2xl font-bold sm:text-3xl">مدیریت سفارش‌ها</h1>
          <p className="mt-2 text-sm text-muted-foreground">مشاهده سفارش‌ها، اقلام، مبالغ و وضعیت پرداخت</p>
        </div>
        <div className="text-sm text-muted-foreground">{count.toLocaleString("fa-IR")} سفارش</div>
      </div>

      <section className="mb-5 grid gap-3 rounded-2xl border border-border bg-card p-4 sm:grid-cols-[minmax(220px,1fr)_180px_180px_auto]">
        <input className={inputClass} value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void load(); }} placeholder="جست‌وجو با شماره سفارش، نام کالا یا SKU" />
        <select className={inputClass} value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">همه وضعیت سفارش</option><option value="pending">در انتظار بررسی</option><option value="confirmed">تأییدشده</option>
        </select>
        <select className={inputClass} value={payment} onChange={(event) => setPayment(event.target.value)}>
          <option value="">همه وضعیت پرداخت</option><option value="unpaid">پرداخت‌نشده</option><option value="paid">پرداخت‌شده</option><option value="failed">ناموفق</option>
        </select>
        <button type="button" className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground" onClick={() => void load()}>اعمال فیلتر</button>
      </section>

      {error && <div role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</div>}

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(340px,.9fr)]">
        <section className="overflow-hidden rounded-2xl border border-border bg-card">
          <div className="border-b border-border px-4 py-3 font-semibold">فهرست سفارش‌ها</div>
          {loading ? <p className="p-8 text-center text-sm text-muted-foreground">در حال دریافت سفارش‌ها…</p> :
            rows.length === 0 ? <p className="p-8 text-center text-sm text-muted-foreground">سفارشی برای نمایش وجود ندارد.</p> : (
              <div className="divide-y divide-border">
                {rows.map((order) => (
                  <button key={order.id} type="button" onClick={() => void openOrder(order)} className={`block w-full p-4 text-right transition hover:bg-muted/60 ${selected?.id === order.id ? "bg-muted" : ""}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <strong>سفارش #{order.id.toLocaleString("fa-IR")}</strong>
                      <span className="text-xs text-muted-foreground">{dateFormat.format(new Date(order.created_at))}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-sm">
                      <span className="text-muted-foreground" dir="ltr">{order.customer_phone}</span>
                      <strong>{money(order.total)}</strong>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full bg-muted px-2.5 py-1">{orderStatus[order.status] ?? order.status}</span>
                      <span className="rounded-full bg-muted px-2.5 py-1">{paymentStatus[order.payment_status] ?? order.payment_status}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          {next && <div className="border-t border-border p-3"><button type="button" className={buttonClass} onClick={() => { const url = new URL(next, window.location.origin); void load(url.pathname + url.search); }}>صفحه بعد</button></div>}
        </section>

        <section className="rounded-2xl border border-border bg-card p-4 sm:p-5">
          {!selected ? <div className="py-10 text-center text-sm text-muted-foreground">برای مشاهده جزئیات، یک سفارش را انتخاب کنید.</div> : (
            <>
              <div className="flex items-center justify-between gap-3 border-b border-border pb-4">
                <div><p className="text-xs text-muted-foreground">جزئیات سفارش</p><h2 className="mt-1 text-xl font-bold">#{selected.id.toLocaleString("fa-IR")}</h2></div>
                <strong>{money(selected.total)}</strong>
              </div>
              <div className="space-y-2 border-b border-border py-4 text-sm">
                <p>وضعیت سفارش: <strong>{orderStatus[selected.status] ?? selected.status}</strong></p>
                <p>وضعیت پرداخت: <strong>{paymentStatus[selected.payment_status] ?? selected.payment_status}</strong></p>
                <p>شناسه حساب مشتری: <span dir="ltr">#{selected.customer_account_id}</span></p>
                <p>تلفن: <span dir="ltr">{selected.customer_phone}</span></p>
                {selected.pii_hidden ? <p className="rounded-lg bg-muted p-3 text-xs leading-6 text-muted-foreground">اطلاعات گیرنده و نشانی برای حساب شما مخفی است. برای مشاهده آن‌ها مجوز orders.view_order_pii لازم است.</p> : (
                  <div className="rounded-lg bg-muted p-3 leading-7">
                    <p>گیرنده: {selected.recipient_name}</p><p>استان و شهر: {selected.province}، {selected.city}</p>
                    <p>نشانی: {selected.address}</p><p>کد پستی: <span dir="ltr">{selected.postal_code}</span></p>
                  </div>
                )}
                <p className="text-xs text-muted-foreground">ثبت: {dateFormat.format(new Date(selected.created_at))}</p>
              </div>
              <h3 className="py-3 font-semibold">اقلام سفارش</h3>
              <div className="space-y-3">
                {selected.items.map((item) => (
                  <article key={item.id} className="rounded-xl border border-border p-3 text-sm">
                    <div className="flex justify-between gap-3"><strong>{item.product_name}</strong><span className="text-xs text-muted-foreground">{item.quantity.toLocaleString("fa-IR")} عدد</span></div>
                    <p className="mt-1 text-xs text-muted-foreground">{item.color_name} · {item.size_label} · <span dir="ltr">{item.sku}</span></p>
                    <div className="mt-2 flex justify-between gap-3"><span>{money(item.unit_price)}</span><strong>{money(item.subtotal)}</strong></div>
                  </article>
                ))}
              </div>
              <p className="mt-4 text-xs leading-6 text-muted-foreground">مبلغ نمایش‌داده‌شده طبق ساختار فعلی سفارش است و هزینه ارسال را شامل نمی‌شود.</p>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
