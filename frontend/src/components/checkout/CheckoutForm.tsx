"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { SignInLink } from "@/components/auth/SignInLink";
import type { Locale } from "@/i18n/config";
import type { CheckoutDictionary } from "@/i18n/dictionaries/checkout";
import { fill } from "@/i18n/dictionaries/checkout";
import { formatCurrency } from "@/lib/format";
import { apiGet, apiPostJson } from "@/lib/checkout/api";
import { EMPTY_DELIVERY, type Cart, type DeliveryField, type DeliveryValues, type Me } from "@/lib/checkout/model";
import { clearGuestCart, guestCartMergePayload } from "@/lib/guest-cart";

type Phase =
  | { kind: "loading" }
  | { kind: "unavailable" }
  | { kind: "signin" }
  | { kind: "empty" }
  | { kind: "ready"; cart: Cart };

async function fetchSnapshot(): Promise<{ phase: Phase; me: Me | null }> {
  const meRes = await apiGet<Me>("/api/auth/me/");
  if (!meRes.ok) {
    const anonymous = meRes.kind === "http" && meRes.status === 401;
    return { phase: { kind: anonymous ? "signin" : "unavailable" }, me: null };
  }

  // Merge only opaque variant IDs + quantities. The server resolves every catalog field and
  // validates active status, price, stock, limits and ownership atomically.
  const guestPayload = guestCartMergePayload();
  if (guestPayload) {
    const merge = await apiPostJson<Cart>("/api/cart/merge-guest/", guestPayload);
    if (!merge.ok) {
      const anonymous = merge.kind === "http" && merge.status === 401;
      return { phase: { kind: anonymous ? "signin" : "unavailable" }, me: meRes.data };
    }
    clearGuestCart();
    const phase: Phase = merge.data.items.length ? { kind: "ready", cart: merge.data } : { kind: "empty" };
    return { phase, me: meRes.data };
  }

  const cartRes = await apiGet<Cart>("/api/cart/");
  if (!cartRes.ok) {
    const anonymous = cartRes.kind === "http" && cartRes.status === 401;
    return { phase: { kind: anonymous ? "signin" : "unavailable" }, me: meRes.data };
  }
  const phase: Phase = cartRes.data.items.length ? { kind: "ready", cart: cartRes.data } : { kind: "empty" };
  return { phase, me: meRes.data };
}

const inputClass = "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground";
const secondaryButton = "inline-flex items-center justify-center rounded-lg border border-border px-4 py-2.5 text-sm hover:bg-muted";

export function CheckoutForm({ locale, t }: { locale: Locale; t: CheckoutDictionary }) {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [me, setMe] = useState<Me | null>(null);
  const [values, setValues] = useState<DeliveryValues>(EMPTY_DELIVERY);

  useEffect(() => {
    let active = true;
    fetchSnapshot().then((snapshot) => {
      if (!active) return;
      setMe(snapshot.me);
      setPhase(snapshot.phase);
    }).catch(() => { if (active) setPhase({ kind: "unavailable" }); });
    return () => { active = false; };
  }, []);

  async function recheck() {
    setPhase({ kind: "loading" });
    try {
      const snapshot = await fetchSnapshot();
      setMe(snapshot.me);
      setPhase(snapshot.phase);
    } catch {
      setPhase({ kind: "unavailable" });
    }
  }

  function setValue(field: DeliveryField, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  if (phase.kind === "loading") {
    return <p role="status" className="mt-6 text-muted-foreground">{t.loading}</p>;
  }

  if (phase.kind === "unavailable") {
    return (
      <Notice title={t.unavailable.title} body={t.unavailable.body}>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={recheck} className={secondaryButton}>{t.unavailable.retry}</button>
          <Link href={`/${locale}/cart`} className={secondaryButton}>{t.unavailable.backToCart}</Link>
        </div>
      </Notice>
    );
  }

  if (phase.kind === "signin") {
    return (
      <Notice title={t.signIn.title} body={t.signIn.body}>
        <SignInLink locale={locale} next={`/${locale}/checkout`} />
      </Notice>
    );
  }

  if (phase.kind === "empty") {
    return (
      <Notice title={t.empty.title} body={t.empty.body}>
        <Link href={`/${locale}/products`} className={secondaryButton}>{t.empty.browse}</Link>
      </Notice>
    );
  }

  const { cart } = phase;
  return (
    <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_20rem]">
      <section className="order-2 grid content-start gap-4 lg:order-1">
        <h2 className="text-xl font-semibold">{t.form.title}</h2>
        {me && <p className="text-sm text-muted-foreground">
          {t.form.phoneNote.split("{phone}")[0]}<bdi dir="ltr">{me.phone}</bdi>
        </p>}
        <form onSubmit={(event) => event.preventDefault()} noValidate className="grid gap-4">
          <Field id="checkout-recipient_name" label={t.form.recipient_name}>
            <input id="checkout-recipient_name" name="recipient_name" autoComplete="name" value={values.recipient_name}
              onChange={(e) => setValue("recipient_name", e.target.value)} className={inputClass} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="checkout-province" label={t.form.province}>
              <input id="checkout-province" name="province" autoComplete="address-level1" value={values.province}
                onChange={(e) => setValue("province", e.target.value)} className={inputClass} />
            </Field>
            <Field id="checkout-city" label={t.form.city}>
              <input id="checkout-city" name="city" autoComplete="address-level2" value={values.city}
                onChange={(e) => setValue("city", e.target.value)} className={inputClass} />
            </Field>
          </div>
          <Field id="checkout-address" label={t.form.address}>
            <textarea id="checkout-address" name="address" autoComplete="street-address" rows={3} value={values.address}
              onChange={(e) => setValue("address", e.target.value)} className={inputClass} />
          </Field>
          <Field id="checkout-postal_code" label={t.form.postal_code} hint={t.form.postalHint}>
            <input id="checkout-postal_code" name="postal_code" autoComplete="postal-code" inputMode="numeric" dir="ltr"
              value={values.postal_code} onChange={(e) => setValue("postal_code", e.target.value)}
              className={`${inputClass} text-start`} />
          </Field>
        </form>
        <p className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm">{t.disabledNote}</p>
      </section>

      <aside aria-labelledby="checkout-summary-title" className="order-1 h-fit rounded-lg border border-border p-4 lg:order-2">
        <h2 id="checkout-summary-title" className="text-lg font-semibold">{t.summary.title}</h2>
        {cart.has_issues && <p role="status" className="mt-3 rounded-lg bg-muted px-3 py-2 text-sm">{t.summary.issues}</p>}
        <ul className="mt-3 divide-y divide-border">
          {cart.items.map((item) => (
            <li key={item.id} className="py-3 text-sm">
              <p className="font-medium">{item.product.name}</p>
              <p className="text-muted-foreground">{item.color.name} · {item.variant_size.label}</p>
              <p className="mt-1 flex justify-between gap-2">
                <span>{fill(t.summary.quantity, { quantity: item.quantity })}</span>
                <span>{formatCurrency(item.subtotal, locale)}</span>
              </p>
              {item.availability === "unavailable" && <p className="mt-1 text-red-700 dark:text-red-400">{t.summary.unavailableLine}</p>}
              {item.availability === "insufficient_stock" && <p className="mt-1 text-red-700 dark:text-red-400">{t.summary.insufficientLine}</p>}
            </li>
          ))}
        </ul>
        <p className="mt-3 flex justify-between border-t border-border pt-3 font-semibold">
          <span>{t.summary.itemsTotal}</span><span data-testid="cart-total">{formatCurrency(cart.total, locale)}</span>
        </p>
        <p className="mt-2 text-xs text-muted-foreground">{t.summary.shippingNote}</p>
      </aside>
    </div>
  );
}

function Notice({ title, body, children }: { title: string; body: string; children: ReactNode }) {
  return <section className="mt-6 rounded-lg border border-border p-6">
    <h2 className="text-xl font-semibold">{title}</h2><p className="mt-2 text-muted-foreground">{body}</p>
    <div className="mt-4">{children}</div>
  </section>;
}

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return <div className="grid gap-1.5">
    <label htmlFor={id} className="text-sm font-medium">{label}{hint && <span className="ms-2 font-normal text-muted-foreground">({hint})</span>}</label>
    {children}
  </div>;
}
