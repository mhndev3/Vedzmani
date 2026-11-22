"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { apiRequest, BrowserApiError } from "@/lib/browser-api";

type Permission = { key: string; app: string; model: string; name: string };
type Role = { id: number; name: string; permissions: string[]; member_count: number; manageable: boolean };
type Staff = { id: number; label: string; is_active: boolean; roles: { id: number; name: string }[]; unmanaged_role_count: number };
type List<T> = { results: T[] };
type RolesResponse = List<Role> & { permissions: Permission[] };

const inputClass = "w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm";
const appLabels: Record<string, string> = { accounts: "حساب‌ها و پشتیبانی", catalog: "کاتالوگ و ویترین", orders: "سفارش و ارسال", inventory: "انبار" };
const modelLabels: Record<string, string> = {
  user: "فهرست مشتریان", supportticket: "تیکت پشتیبانی", supportticketmessage: "پاسخ پشتیبانی",
  adminauditevent: "تاریخچه فعالیت", product: "محصول", category: "دسته‌بندی", collection: "مجموعه",
  size: "سایز", colorvariant: "رنگ محصول", variantsize: "ترکیب رنگ و سایز", variantimage: "تصاویر محصول",
  productsizemeasurement: "اندازه‌های محصول", productsizedescription: "توضیحات سایز محصول",
  variantsizemeasurement: "اندازه ترکیب رنگ و سایز", variantsizedescription: "توضیحات ترکیب رنگ و سایز",
  homepagebanner: "بنر صفحه اصلی", homepagesection: "بخش صفحه اصلی", storefronttheme: "قالب فروشگاه",
  order: "سفارش", orderitem: "اقلام سفارش", shippingmethod: "روش ارسال", inventoryadjustment: "تعدیل موجودی",
};
const actionLabels: Record<string, string> = { view: "مشاهده", add: "ایجاد", change: "ویرایش", delete: "حذف", view_order_pii: "مشاهده اطلاعات شخصی سفارش" };

function permissionLabel(permission: Permission) {
  const action = permission.key.split(".")[1].replace(/_([a-z0-9_]+)$/, "");
  const model = permission.model;
  const codename = permission.key.split(".")[1];
  const actionText = codename === "view_order_pii" ? actionLabels.view_order_pii : actionLabels[action] || action;
  return `${modelLabels[model] || permission.name} · ${actionText}`;
}

export default function AdminStaffRolesPage() {
  const params = useParams<{ locale: string }>();
  const locale = params.locale || "fa";
  const [roles, setRoles] = useState<Role[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<number | null>(null);
  const [roleName, setRoleName] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [roleDrafts, setRoleDrafts] = useState<Record<number, number[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [roleData, staffData] = await Promise.all([
        apiRequest<RolesResponse>("GET", "/api/admin/staff/roles/"),
        apiRequest<List<Staff>>("GET", "/api/admin/staff/"),
      ]);
      setRoles(roleData.results);
      setPermissions(roleData.permissions);
      setStaff(staffData.results);
      setRoleDrafts(Object.fromEntries(staffData.results.map(person => [person.id, person.roles.map(role => role.id)])));
    } catch (e) {
      setError(e instanceof BrowserApiError && e.status === 403
        ? "این بخش فقط برای مدیر ارشد قابل دسترسی است."
        : "دریافت اطلاعات نقش‌ها و مدیران ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void Promise.resolve().then(load); }, [load]);

  const selectedRole = roles.find(role => role.id === selectedRoleId) || null;

  const permissionsByApp = useMemo(() => {
    const grouped: Record<string, Permission[]> = {};
    for (const permission of permissions) (grouped[permission.app] ||= []).push(permission);
    return grouped;
  }, [permissions]);

  const togglePermission = (key: string) => {
    setSelectedPermissions(current => current.includes(key) ? current.filter(item => item !== key) : [...current, key]);
  };

  const saveRole = async () => {
    setSaving(true); setError(""); setNotice("");
    try {
      if (selectedRole) {
        await apiRequest<Role>("PATCH", `/api/admin/staff/roles/${selectedRole.id}/`, { name: roleName, permissions: selectedPermissions });
        setNotice("نقش با موفقیت به‌روزرسانی شد.");
      } else {
        const created = await apiRequest<Role>("POST", "/api/admin/staff/roles/", { name: roleName, permissions: selectedPermissions });
        setSelectedRoleId(created.id);
        setNotice("نقش جدید ساخته شد.");
      }
      await load();
    } catch (e) {
      setError(e instanceof BrowserApiError && e.status === 409 ? "نام نقش تکراری است یا نقش در وضعیت قابل ویرایش نیست." : "ذخیره نقش انجام نشد.");
    } finally { setSaving(false); }
  };

  const deleteRole = async () => {
    if (!selectedRole) return;
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<void>("DELETE", `/api/admin/staff/roles/${selectedRole.id}/`);
      setSelectedRoleId(null);
      setRoleName("");
      setSelectedPermissions([]);
      setNotice("نقش حذف شد.");
      await load();
    } catch (e) {
      setError(e instanceof BrowserApiError && e.status === 409 ? "این نقش به مدیران اختصاص داده شده و قابل حذف نیست." : "حذف نقش انجام نشد.");
    } finally { setSaving(false); }
  };

  const saveStaffRoles = async (person: Staff) => {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest<Staff>("PATCH", `/api/admin/staff/${person.id}/roles/`, { role_ids: roleDrafts[person.id] || [] });
      setNotice(`نقش‌های ${person.label} ذخیره شد.`);
      await load();
    } catch {
      setError("ذخیره نقش‌های مدیر انجام نشد.");
    } finally { setSaving(false); }
  };

  return (
    <main dir="rtl" className="mx-auto w-full max-w-7xl px-4 py-8 sm:py-10">
      <Link href={`/${locale}/admin-panel`} className="text-sm text-muted-foreground hover:text-foreground">← بازگشت به پنل مدیریت</Link>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-bold sm:text-3xl">مدیریت مدیران و نقش‌ها</h1><p className="mt-2 text-sm leading-7 text-muted-foreground">تعریف نقش، تعیین مجوزهای هر نقش و تخصیص آن به مدیران موجود</p></div>
        <button type="button" onClick={() => void load()} className="rounded-xl border border-border px-4 py-2.5 text-sm">به‌روزرسانی</button>
      </div>
      <p className="mt-4 rounded-xl border border-border bg-muted/30 p-3 text-xs leading-6 text-muted-foreground">این بخش فقط در اختیار مدیر ارشد است. ایجاد حساب مدیر، تغییر رمز و ارتقای حساب به مدیر ارشد از این صفحه ممکن نیست. مجوزهای پرداخت، احراز هویت و مدیریت کاربران نیز قابل واگذاری نیستند.</p>
      {error && <p role="alert" className="mt-4 rounded-xl border border-destructive/40 p-3 text-sm">{error}</p>}
      {notice && <p role="status" className="mt-4 rounded-xl border border-border p-3 text-sm">{notice}</p>}
      {loading ? <p className="py-16 text-center text-sm text-muted-foreground">در حال دریافت اطلاعات…</p> : !error && (
        <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,.9fr)]">
          <section className="rounded-2xl border border-border bg-card p-4 sm:p-5">
            <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-bold">نقش‌ها و مجوزها</h2><button type="button" onClick={() => { setSelectedRoleId(null); setRoleName(""); setSelectedPermissions([]); }} className="rounded-lg border border-border px-3 py-2 text-xs">نقش جدید</button></div>
            <div className="mt-3 flex flex-wrap gap-2">
              {roles.map(role => <button key={role.id} type="button" onClick={() => { setSelectedRoleId(role.id); setRoleName(role.name); setSelectedPermissions(role.permissions); }} className={`rounded-lg border px-3 py-2 text-sm ${selectedRoleId === role.id ? "border-primary bg-primary/10" : "border-border"}`}>{role.name} <span className="text-xs text-muted-foreground">({role.member_count})</span></button>)}
            </div>
            <div className="mt-5 border-t border-border pt-5">
              <label className="mb-2 block text-sm font-medium" htmlFor="role-name">نام نقش</label>
              <input id="role-name" className={inputClass} maxLength={80} value={roleName} onChange={e => setRoleName(e.target.value)} placeholder="مثلاً مدیر پشتیبانی"/>
              <div className="mt-5 space-y-5">
                {Object.entries(permissionsByApp).map(([app, items]) => <fieldset key={app}>
                  <legend className="mb-2 text-sm font-semibold">{appLabels[app] || app}</legend>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {items.map(permission => <label key={permission.key} className="flex items-center gap-2 rounded-lg border border-border p-2.5 text-xs">
                      <input type="checkbox" checked={selectedPermissions.includes(permission.key)} onChange={() => togglePermission(permission.key)} />
                      <span>{permissionLabel(permission)}</span>
                    </label>)}
                  </div>
                </fieldset>)}
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                <button type="button" disabled={saving || !roleName.trim()} onClick={() => void saveRole()} className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50">{saving ? "در حال ذخیره…" : selectedRole ? "ذخیره تغییرات نقش" : "ایجاد نقش"}</button>
                {selectedRole && <button type="button" disabled={saving || selectedRole.member_count > 0} onClick={() => void deleteRole()} className="rounded-xl border border-destructive/40 px-4 py-2.5 text-sm text-destructive disabled:opacity-40">حذف نقش</button>}
              </div>
              {selectedRole?.member_count ? <p className="mt-2 text-xs text-muted-foreground">برای حذف این نقش، ابتدا آن را از همه مدیران بردارید.</p> : null}
            </div>
          </section>
          <section className="rounded-2xl border border-border bg-card p-4 sm:p-5">
            <h2 className="font-bold">تخصیص نقش به مدیران</h2>
            <p className="mt-1 text-xs leading-6 text-muted-foreground">فقط حساب‌های دارای دسترسی staff نمایش داده می‌شوند. مدیران ارشد در این فهرست قابل تغییر نیستند. نقش‌های خارج از این بخش هنگام ذخیره حفظ می‌شوند.</p>
            <div className="mt-4 space-y-4">
              {staff.length === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">حساب مدیر دیگری ثبت نشده است.</p> : staff.map(person => <div key={person.id} className="rounded-xl border border-border p-3">
                <div className="flex items-center justify-between gap-2"><strong className="text-sm">{person.label}</strong><span className={`text-xs ${person.is_active ? "text-muted-foreground" : "text-destructive"}`}>{person.is_active ? "فعال" : "غیرفعال"}</span></div>
                {person.unmanaged_role_count > 0 && <p className="mt-2 text-xs text-muted-foreground">{person.unmanaged_role_count.toLocaleString("fa-IR")} نقش خارج از این بخش بدون تغییر حفظ می‌شود.</p>}\n                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {roles.map(role => <label key={role.id} className="flex items-center gap-2 text-xs">
                    <input type="checkbox" checked={(roleDrafts[person.id] || []).includes(role.id)} onChange={e => setRoleDrafts(current => ({...current, [person.id]: e.target.checked ? [...(current[person.id] || []), role.id] : (current[person.id] || []).filter(id => id !== role.id)}))}/>
                    <span>{role.name}</span>
                  </label>)}
                </div>
                <button type="button" disabled={saving} onClick={() => void saveStaffRoles(person)} className="mt-3 rounded-lg border border-border px-3 py-2 text-xs disabled:opacity-50">ذخیره نقش‌های مدیر</button>
              </div>)}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
