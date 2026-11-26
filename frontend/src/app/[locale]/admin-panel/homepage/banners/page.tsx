"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import Image from "next/image";
import { useParams } from "next/navigation";
import { apiMultipartRequest, apiRequest, BrowserApiError } from "@/lib/browser-api";

type BannerGroup = { id: number; slug: string; is_active: boolean };
type Banner = { id: number; group: number; alt_text: string; desktop_image_url: string; status: "draft" | "published"; position: number };

const fieldClass = "mt-2 w-full rounded-xl border border-border bg-background px-3 py-3 text-sm text-foreground file:ml-3 file:rounded-lg file:border-0 file:bg-muted file:px-3 file:py-2 file:text-sm";
const primaryClass = "rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50";

function errorMessage(error: unknown) {
  if (error instanceof BrowserApiError && (error.status === 401 || error.status === 403)) return "مجوز تغییر بنر صفحه اصلی را ندارید.";
  if (error instanceof BrowserApiError && error.status === 400) return "تصویر انتخاب‌شده معتبر نیست. فرمت JPEG، PNG یا WebP و حداکثر حجم ۸ مگابایت مجاز است.";
  if (error instanceof BrowserApiError && error.status === 0) return "ارتباط با سرور برقرار نشد.";
  return "تغییر بنر ذخیره نشد. دوباره تلاش کنید.";
}

export default function AdminHomepageBannersPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [banner, setBanner] = useState<Banner | null>(null);
  const [groupId, setGroupId] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadBanner = useCallback(async () => {
    const [groups, banners] = await Promise.all([
      apiRequest<BannerGroup[]>("GET", "/api/admin/homepage/banner-groups/"),
      apiRequest<Banner[]>("GET", "/api/admin/homepage/banners/"),
    ]);
    const mainGroup = groups.find(group => group.slug === "main" && group.is_active)
      ?? groups.find(group => group.is_active);
    if (!mainGroup) throw new Error("گروه اصلی بنر صفحه اصلی پیدا نشد.");
    const current = banners
      .filter(item => item.group === mainGroup.id && item.status === "published")
      .sort((a, b) => a.position - b.position || a.id - b.id)[0] ?? null;
    return { groupId: mainGroup.id, banner: current };
  }, []);

  useEffect(() => {
    let active = true;
    void loadBanner()
      .then(({ groupId: nextGroupId, banner: nextBanner }) => {
        if (!active) return;
        setGroupId(nextGroupId);
        setBanner(nextBanner);
      })
      .catch(cause => { if (active) setError(errorMessage(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [loadBanner]);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) { setError("ابتدا تصویر جدید بنر را انتخاب کنید."); return; }
    setSaving(true);
    setError("");
    setNotice("");
    const data = new FormData();
    data.set("desktop_image", file);
    data.set("status", "published");
    data.set("alt_text", banner?.alt_text || "بنر صفحه اصلی ودزمانی");
    try {
      if (banner) {
        await apiMultipartRequest("PATCH", `/api/admin/homepage/banners/${banner.id}/`, data);
      } else {
        if (!groupId) throw new Error("گروه فعال بنر در دسترس نیست.");
        data.set("group", String(groupId));
        data.set("position", "0");
        await apiMultipartRequest("POST", "/api/admin/homepage/banners/", data);
      }
      setFile(null);
      setPreview("");
      const updated = await loadBanner();
      setGroupId(updated.groupId);
      setBanner(updated.banner);
      setNotice("بنر جدید ذخیره و در صفحه اصلی منتشر شد.");
    } catch (cause) {
      setError(cause instanceof Error && !(cause instanceof BrowserApiError) ? cause.message : errorMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <main dir="rtl" className="admin-panel mx-auto w-full max-w-3xl px-4 py-8 sm:py-10">
      <div className="mb-7">
        <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
        <h1 className="mt-3 text-2xl font-bold text-foreground sm:text-3xl">تغییر بنر صفحه اصلی</h1>
        <p className="mt-2 text-sm leading-7 text-muted-foreground">فقط تصویر جدید را انتخاب و ذخیره کنید. بنر قبلی تا زمان ذخیره تصویر جدید در سایت باقی می‌ماند.</p>
      </div>

      {notice && <p role="status" className="mb-4 rounded-xl border border-border bg-muted p-3 text-sm text-foreground">{notice}</p>}
      {error && <p role="alert" className="mb-4 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}

      <section className="rounded-2xl border border-border bg-card p-5 sm:p-6">
        <h2 className="font-semibold text-foreground">بنر فعلی سایت</h2>
        {loading ? <p className="py-12 text-center text-sm text-muted-foreground">در حال دریافت بنر…</p> : banner ? (
          <div className="relative mt-4 aspect-[2048/746] overflow-hidden rounded-xl bg-muted">
            <Image src={preview || banner.desktop_image_url} alt="پیش‌نمایش بنر صفحه اصلی" fill sizes="(max-width: 768px) 100vw, 720px" unoptimized className="object-cover" />
          </div>
        ) : (
          <div className="mt-4 flex aspect-[2048/746] items-center justify-center rounded-xl border border-dashed border-border bg-muted text-sm text-muted-foreground">هنوز بنر منتشرشده‌ای ثبت نشده است.</div>
        )}
        <form onSubmit={save} className="mt-5 space-y-4">
          <label className="block text-sm font-medium text-foreground">
            تصویر جدید بنر (JPEG، PNG یا WebP، حداکثر ۸ مگابایت)
            <input type="file" accept="image/jpeg,image/png,image/webp" required onChange={event => {
              const nextFile = event.target.files?.[0] ?? null;
              setPreview(nextFile ? URL.createObjectURL(nextFile) : "");
              setFile(nextFile);
            }} className={fieldClass} />
          </label>
          {preview && <p className="text-xs text-muted-foreground">پیش‌نمایش تصویر انتخاب‌شده نمایش داده می‌شود؛ تصویر فعلی تا زمان ذخیره تغییر نمی‌کند.</p>}
          <button type="submit" disabled={saving || loading || !file} className={primaryClass}>{saving ? "در حال ذخیره…" : "ذخیره و انتشار بنر"}</button>
        </form>
      </section>
    </main>
  );
}
