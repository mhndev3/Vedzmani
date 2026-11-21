"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Customer = {
  id: number;
  phone_masked: string;
  is_active: boolean;
  date_joined: string;
  order_count: number;
  total_spent: string;
  pii_hidden: boolean;
};
type Page = { count: number; next: string | null; previous: string | null; results: Customer[] };

const inputClass = "rounded-xl border border-border bg-background px-3 py-2.5 text-sm";
const buttonClass = "rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50";
const dateFormat = new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short" });
const money = (value: string) => Number(value).toLocaleString("fa-IR") + " تومان";

function errorText(error: unknown) {
  if (error instanceof BrowserApiError && error.status === 403) return "مجوز مشاهده فهرست مشتریان برای حساب شما فعال نیست.";
  if (error instanceof BrowserApiError && error.status === 401) return "نشست ورود منقضی شده است. دوباره وارد حساب مدیریت شوید.";
  return "دریافت اطلاعات مشتریان با خطا مواجه شد.";
}

export default function AdminCustomersPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [rows, setRows] = useState<Customer[]>([]);
  const [selected, setSelected] = useState<Customer | null>(null);
  const [count, setCount] = useState(0);
  const [next, setNext] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [active, setActive] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (url?: string) => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams();
      if (search.trim()) query.set("search", search.trim());
      if (active) query.set("active", active);
      const target = url ?? "/api/admin/customers/?" + query.toString();
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
  }, [active, search]);

  useEffect(() => {
    void Promise.resolve().then(() => load());
  }, [load]);

  async function openCustomer(customer: Customer) {
    setSelected(customer);
    try {
      const detail = await apiRequest<Customer>("GET", `/api/admin/customers/${customer.id}/`);
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
          <h1 className="mt-3 text-2xl font-bold sm:text-3xl">مدیریت مشتریان</h1>
          <p className="mt-2 text-sm text-muted-foreground">فهرست حساب‌ها، وضعیت عضویت و خلاصه سفارش‌های هر مشتری</p>
        </div>
        <div className="text-sm text-muted-foreground">{count.toLocaleString("fa-IR")} مشتری</div>
      </div>

      <section className="mb-5 grid gap-3 rounded-2xl border border-border bg-card p-4 sm:grid-cols-[minmax(220px,1fr)_200px_auto]">
        <input className={inputClass} inputMode="numeric" value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void load(); }} placeholder="جست‌وجو با شناسه حساب مشتری" />
        <select className={inputClass} value={active} onChange={(event) => setActive(event.target.value)}>
          <option value="">همه حساب‌ها</option><option value="true">حساب‌های فعال</option><option value="false">حساب‌های غیرفعال</option>
        </select>
        <button type="button" className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground" onClick={() => void load()}>اعمال فیلتر</button>
      </section>

      {error && <div role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</div>}

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,.9fr)]">
        <section className="overflow-hidden rounded-2xl border border-border bg-card">
          <div className="border-b border-border px-4 py-3 font-semibold">فهرست مشتریان</div>
          {loading ? <p className="p-8 text-center text-sm text-muted-foreground">در حال دریافت مشتریان…</p> :
            rows.length === 0 ? <p className="p-8 text-center text-sm text-muted-foreground">مشتری‌ای برای نمایش وجود ندارد.</p> : (
              <div className="divide-y divide-border">
                {rows.map((customer) => (
                  <button key={customer.id} type="button" onClick={() => void openCustomer(customer)} className={`block w-full p-4 text-right transition hover:bg-muted/60 ${selected?.id === customer.id ? "bg-muted" : ""}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <strong>مشتری #{customer.id.toLocaleString("fa-IR")}</strong>
                      <span className={`rounded-full px-2.5 py-1 text-xs ${customer.is_active ? "bg-emerald-500/10 text-emerald-700" : "bg-muted text-muted-foreground"}`}>{customer.is_active ? "فعال" : "غیرفعال"}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-sm">
                      <span dir="ltr" className="text-muted-foreground">{customer.phone_masked}</span>
                      <span>{customer.order_count.toLocaleString("fa-IR")} سفارش</span>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">عضویت: {dateFormat.format(new Date(customer.date_joined))}</p>
                  </button>
                ))}
              </div>
            )}
          {next && <div className="border-t border-border p-3"><button type="button" className={buttonClass} onClick={() => { const url = new URL(next, window.location.origin); void load(url.pathname + url.search); }}>صفحه بعد</button></div>}
        </section>

        <section className="rounded-2xl border border-border bg-card p-4 sm:p-5">
          {!selected ? <div className="py-10 text-center text-sm text-muted-foreground">برای مشاهده خلاصه حساب، یک مشتری را انتخاب کنید.</div> : (
            <>
              <div className="border-b border-border pb-4">
                <p className="text-xs text-muted-foreground">خلاصه حساب مشتری</p>
                <h2 className="mt-1 text-xl font-bold">مشتری #{selected.id.toLocaleString("fa-IR")}</h2>
                <p className="mt-2 text-sm text-muted-foreground" dir="ltr">{selected.phone_masked}</p>
              </div>
              <dl className="grid grid-cols-2 gap-3 py-4 text-sm">
                <div className="rounded-xl bg-muted p-3"><dt className="text-muted-foreground">وضعیت حساب</dt><dd className="mt-1 font-semibold">{selected.is_active ? "فعال" : "غیرفعال"}</dd></div>
                <div className="rounded-xl bg-muted p-3"><dt className="text-muted-foreground">تعداد سفارش</dt><dd className="mt-1 font-semibold">{selected.order_count.toLocaleString("fa-IR")}</dd></div>
                <div className="col-span-2 rounded-xl bg-muted p-3"><dt className="text-muted-foreground">مجموع مبالغ سفارش ثبت‌شده</dt><dd className="mt-1 font-semibold">{money(selected.total_spent)}</dd></div>
              </dl>
              <p className="text-xs leading-6 text-muted-foreground">تاریخ عضویت: {dateFormat.format(new Date(selected.date_joined))}</p>
              <p className="mt-3 rounded-xl border border-border p-3 text-xs leading-6 text-muted-foreground">اطلاعات تماس کامل، نشانی و کد ملی در این بخش نمایش داده نمی‌شود. شماره تلفن و اطلاعات تحویل فقط طبق مجوز مستقل اطلاعات شخصی در فضای سفارش‌ها قابل مشاهده است.</p>
              <Link href={`/${locale}/admin-panel/orders`} className="mt-4 inline-flex rounded-xl border border-border px-3 py-2 text-sm hover:bg-muted">رفتن به مدیریت سفارش‌ها</Link>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
