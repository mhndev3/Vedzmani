"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { BrowserApiError } from "@/lib/browser-api";
import type { Locale } from "@/i18n/config";
import { authApi, type CustomerProfile, type CustomerProfileInput } from "@/lib/auth/api";

type Props = { initialProfile: CustomerProfile; locale: Locale };
const field = "w-full rounded-lg border border-border bg-background px-3 py-2.5 text-base placeholder:text-muted-foreground";

export function ProfileForm({ initialProfile, locale }: Props) {
  const router = useRouter();
  const [values, setValues] = useState<CustomerProfileInput>({
    first_name: initialProfile.first_name,
    last_name: initialProfile.last_name,
    address: initialProfile.address,
    postal_code: initialProfile.postal_code,
    national_code: initialProfile.national_code ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function update(name: keyof CustomerProfileInput, value: string) {
    setValues((current) => ({ ...current, [name]: value }));
    setError(null);
    setMessage(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!/^[0-9۰-۹٠-٩]{10}$/.test(values.national_code)) {
      setError("کد ملی باید دقیقاً ۱۰ رقم باشد.");
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await authApi.updateProfile(values);
      setMessage("اطلاعات حساب با موفقیت ذخیره شد.");
      router.refresh();
    } catch (cause) {
      if (cause instanceof BrowserApiError && cause.code === "validation_error") {
        const code = cause.details?.national_code?.[0]?.code;
        setError(code === "unique" ? "این کد ملی قبلاً برای حساب دیگری ثبت شده است." : "اطلاعات واردشده را بررسی کنید.");
      } else {
        setError("ذخیره اطلاعات انجام نشد. اتصال را بررسی کنید و دوباره تلاش کنید.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function logout() {
    setLoggingOut(true);
    try {
      await authApi.logout();
      router.replace("/" + locale);
      router.refresh();
    } catch {
      setError("خروج از حساب انجام نشد. دوباره تلاش کنید.");
      setLoggingOut(false);
    }
  }

  const input = (name: keyof CustomerProfileInput, label: string, options: { maxLength?: number; dir?: "ltr" | "rtl"; multiline?: boolean; hint?: string } = {}) => (
    <div className="grid gap-1.5">
      <label htmlFor={name} className="text-sm font-medium">{label}</label>
      {options.multiline ? (
        <textarea id={name} name={name} required maxLength={options.maxLength ?? 1000} rows={4} value={values[name]} onChange={(event) => update(name, event.target.value)} className={field} />
      ) : (
        <input id={name} name={name} required maxLength={options.maxLength} dir={options.dir} inputMode={name === "national_code" || name === "postal_code" ? "numeric" : undefined} autoComplete={name === "first_name" ? "given-name" : name === "last_name" ? "family-name" : name === "postal_code" ? "postal-code" : undefined} value={values[name]} onChange={(event) => update(name, event.target.value)} className={field} />
      )}
      {options.hint && <p className="text-xs text-muted-foreground">{options.hint}</p>}
    </div>
  );

  return (
    <section className="mt-8 rounded-2xl border border-border p-5 sm:p-7">
      <div className="mb-6">
        <h2 className="text-lg font-semibold">{initialProfile.is_complete ? "اطلاعات حساب کاربری" : "تکمیل اطلاعات حساب کاربری"}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{initialProfile.is_complete ? "اطلاعات حساب خود را مشاهده و در صورت نیاز ویرایش کنید." : "برای تکمیل ثبت‌نام، تمام فیلدهای زیر الزامی هستند."}</p>
      </div>
      {message && <p role="status" className="mb-4 rounded-lg bg-muted p-3 text-sm">{message}</p>}
      {error && <p role="alert" className="mb-4 rounded-lg border border-destructive/40 p-3 text-sm">{error}</p>}
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        {input("first_name", "نام")}
        {input("last_name", "نام خانوادگی")}
        <div className="sm:col-span-2">{input("address", "نشانی کامل", { multiline: true, maxLength: 1000 })}</div>
        {input("postal_code", "کد پستی", { dir: "ltr", maxLength: 20 })}
        {input("national_code", "کد ملی", { dir: "ltr", maxLength: 10, hint: "کد ملی باید دقیقاً ۱۰ رقم باشد." })}
        <div className="flex flex-wrap items-center gap-3 pt-2 sm:col-span-2">
          <button type="submit" disabled={saving || loggingOut} className="inline-flex h-11 items-center justify-center rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground disabled:opacity-60">
            {saving ? "در حال ذخیره…" : "ذخیره اطلاعات"}
          </button>
          <button type="button" onClick={() => void logout()} disabled={saving || loggingOut} className="inline-flex h-11 items-center justify-center rounded-lg border border-border px-5 text-sm hover:bg-muted disabled:opacity-60">
            {loggingOut ? "در حال خروج…" : "خروج از حساب"}
          </button>
        </div>
      </form>
    </section>
  );
}
