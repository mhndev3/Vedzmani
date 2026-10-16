"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent, type ReactNode, type RefObject } from "react";
import type { Locale } from "@/i18n/config";
import { fill, type CheckoutDictionary } from "@/i18n/dictionaries/checkout";
import { apiGet, apiPostJson, type ApiDetails } from "@/lib/checkout/api";
import {
  DELIVERY_FIELDS,
  EMPTY_DELIVERY,
  MAX_LENGTH,
  fieldErrorFromServerCode,
  isConfirmedOrder,
  validateDelivery,
  type Cart,
  type DeliveryField,
  type DeliveryValues,
  type FieldErrors,
  type Me,
  type Order,
} from "@/lib/checkout/model";

type Phase =
  | { kind: "loading" }
  | { kind: "unavailable" }
  | { kind: "signin" }
  | { kind: "empty" }
  // Cart is empty right after a submit whose outcome is unknown or was a repeat: do not re-order blindly.
  | { kind: "maybePlaced" }
  | { kind: "ready"; cart: Cart }
  | { kind: "placed"; order: Order };

type Banner = keyof CheckoutDictionary["banners"];
type Snapshot = { phase: Phase; me: Me | null };

/** Reads who is signed in and the server-side cart. Django is the only source of truth for both. */
async function fetchSnapshot(): Promise<Snapshot> {
  const meRes = await apiGet<Me>("/api/auth/me/");
  if (!meRes.ok) {
    const anonymous = meRes.kind === "http" && meRes.status === 401;
    return { phase: { kind: anonymous ? "signin" : "unavailable" }, me: null };
  }
  const cartRes = await apiGet<Cart>("/api/cart/");
  if (!cartRes.ok) {
    const anonymous = cartRes.kind === "http" && cartRes.status === 401;
    return { phase: { kind: anonymous ? "signin" : "unavailable" }, me: meRes.data };
  }
  const phase: Phase =
    cartRes.data.items.length === 0 ? { kind: "empty" } : { kind: "ready", cart: cartRes.data };
  return { phase, me: meRes.data };
}

function formatMoney(value: string, locale: Locale): string {
  // Display only. Whole-unit Decimal strings come from Django; no arithmetic happens here.
  if (!/^\d+$/.test(value)) return value; // never the case per contract; show it verbatim rather than guess
  return new Intl.NumberFormat(locale === "fa" ? "fa-IR" : "en-US", {
    maximumFractionDigits: 0,
  }).format(BigInt(value));
}

function fieldErrorsFromDetails(details: ApiDetails | undefined): FieldErrors {
  const errors: FieldErrors = {};
  if (!details) return errors;
  for (const field of DELIVERY_FIELDS) {
    const first = details[field]?.[0];
    if (first) errors[field] = fieldErrorFromServerCode(first.code);
  }
  return errors;
}

const inputClass =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground";
const primaryButton =
  "inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60";
const secondaryButton =
  "inline-flex items-center justify-center rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted";

export function CheckoutForm({ locale, t }: { locale: Locale; t: CheckoutDictionary }) {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [me, setMe] = useState<Me | null>(null);
  const [values, setValues] = useState<DeliveryValues>(EMPTY_DELIVERY);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [banner, setBanner] = useState<Banner | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inFlight = useRef(false); // synchronous guard: state updates are too late to stop a double click
  const alive = useRef(true);
  const confirmationHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    alive.current = true;
    fetchSnapshot().then((snapshot) => {
      if (!alive.current) return;
      setMe(snapshot.me);
      setPhase(snapshot.phase);
    });
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    if (phase.kind === "placed") confirmationHeading.current?.focus();
  }, [phase.kind]);

  async function recheck() {
    setPhase({ kind: "loading" });
    const snapshot = await fetchSnapshot();
    if (!alive.current) return;
    setMe(snapshot.me);
    setPhase(snapshot.phase);
  }

  /** Re-reads the cart after a failed or unconfirmed submit. Entered values are never touched. */
  async function refreshAfterSubmit(unknownOutcome: boolean) {
    const snapshot = await fetchSnapshot();
    if (!alive.current) return;
    if (snapshot.me) setMe(snapshot.me);
    if (snapshot.phase.kind === "unavailable") return; // transient: keep what the customer sees
    if (snapshot.phase.kind === "empty" && unknownOutcome) setPhase({ kind: "maybePlaced" });
    else setPhase(snapshot.phase);
  }

  function setValue(field: DeliveryField, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => (current[field] ? { ...current, [field]: undefined } : current));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || phase.kind !== "ready") return;

    const localErrors = validateDelivery(values);
    const firstInvalid = DELIVERY_FIELDS.find((field) => localErrors[field]);
    if (firstInvalid) {
      setFieldErrors(localErrors);
      setBanner(null);
      document.getElementById(`checkout-${firstInvalid}`)?.focus();
      return;
    }

    inFlight.current = true;
    setSubmitting(true);
    setBanner(null);
    setFieldErrors({});
    try {
      const body = Object.fromEntries(DELIVERY_FIELDS.map((field) => [field, values[field].trim()]));
      const res = await apiPostJson<unknown>("/api/orders/", body);

      if (res.ok) {
        if (res.status === 201 && isConfirmedOrder(res.data)) {
          setPhase({ kind: "placed", order: res.data });
        } else {
          // Success status but no valid order body: never claim success we cannot show.
          setBanner("ambiguous");
          await refreshAfterSubmit(true);
        }
        return;
      }
      if (res.kind === "network" || res.status >= 500) {
        setBanner("ambiguous");
        await refreshAfterSubmit(true);
        return;
      }
      if (res.code === "csrf_unavailable") return void setBanner("csrfUnavailable");
      if (res.status === 401) return void setPhase({ kind: "signin" });
      if (res.status === 403 && res.code === "csrf_failed") return void setBanner("csrf");
      if (res.status === 400 && res.code === "validation_error") {
        const serverErrors = fieldErrorsFromDetails(res.details);
        if (Object.keys(serverErrors).length > 0) {
          setFieldErrors(serverErrors);
          const first = DELIVERY_FIELDS.find((field) => serverErrors[field]);
          if (first) document.getElementById(`checkout-${first}`)?.focus();
        } else setBanner("server");
        return;
      }
      if (res.status === 400 && res.code === "empty_cart") {
        setPhase({ kind: "maybePlaced" });
        return;
      }
      if (res.status === 409 && (res.code === "item_unavailable" || res.code === "insufficient_stock")) {
        setBanner(res.code);
        await refreshAfterSubmit(false);
        return;
      }
      setBanner("server");
    } finally {
      inFlight.current = false;
      if (alive.current) setSubmitting(false);
    }
  }

  const errorText = (field: DeliveryField): string | null => {
    const code = fieldErrors[field];
    if (!code) return null;
    return fill(t.fieldErrors[code], { max: MAX_LENGTH[field] });
  };

  if (phase.kind === "loading") {
    return (
      <p role="status" className="mt-6 text-muted-foreground">
        {t.loading}
      </p>
    );
  }

  if (phase.kind === "unavailable") {
    return (
      <Notice title={t.unavailable.title} body={t.unavailable.body}>
        <button type="button" onClick={recheck} className={secondaryButton}>
          {t.unavailable.retry}
        </button>
      </Notice>
    );
  }

  if (phase.kind === "signin") {
    return (
      <Notice title={t.signIn.title} body={t.signIn.body}>
        <button type="button" onClick={recheck} className={secondaryButton}>
          {t.signIn.recheck}
        </button>
      </Notice>
    );
  }

  if (phase.kind === "empty" || phase.kind === "maybePlaced") {
    const copy = phase.kind === "empty" ? t.empty : t.maybePlaced;
    return (
      <Notice title={copy.title} body={copy.body}>
        <Link href={`/${locale}/products`} className={secondaryButton}>
          {copy.browse}
        </Link>
      </Notice>
    );
  }

  if (phase.kind === "placed") {
    return <Confirmation order={phase.order} locale={locale} t={t} headingRef={confirmationHeading} />;
  }

  const { cart } = phase;
  const hasFieldErrors = DELIVERY_FIELDS.some((field) => fieldErrors[field]);

  return (
    <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_20rem]">
      <form onSubmit={onSubmit} noValidate aria-busy={submitting} className="order-2 grid gap-4 lg:order-1">
        <h2 className="text-xl font-semibold">{t.form.title}</h2>
        {banner && (
          <p role="alert" className="rounded-lg border border-border bg-muted px-4 py-3 text-sm">
            {t.banners[banner]}
          </p>
        )}
        {hasFieldErrors && (
          <p role="alert" className="text-sm font-medium text-red-700 dark:text-red-400">
            {t.errorsTitle}
          </p>
        )}
        {me && (
          <p className="text-sm text-muted-foreground">
            {t.form.phoneNote.split("{phone}")[0]}
            <bdi dir="ltr">{me.phone}</bdi>
          </p>
        )}

        <Field id="checkout-recipient_name" label={t.form.recipient_name} error={errorText("recipient_name")}>
          <input
            id="checkout-recipient_name"
            name="recipient_name"
            autoComplete="name"
            value={values.recipient_name}
            onChange={(e) => setValue("recipient_name", e.target.value)}
            className={inputClass}
            aria-invalid={Boolean(fieldErrors.recipient_name)}
            aria-describedby={fieldErrors.recipient_name ? "checkout-recipient_name-error" : undefined}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="checkout-province" label={t.form.province} error={errorText("province")}>
            <input
              id="checkout-province"
              name="province"
              autoComplete="address-level1"
              value={values.province}
              onChange={(e) => setValue("province", e.target.value)}
              className={inputClass}
              aria-invalid={Boolean(fieldErrors.province)}
              aria-describedby={fieldErrors.province ? "checkout-province-error" : undefined}
            />
          </Field>
          <Field id="checkout-city" label={t.form.city} error={errorText("city")}>
            <input
              id="checkout-city"
              name="city"
              autoComplete="address-level2"
              value={values.city}
              onChange={(e) => setValue("city", e.target.value)}
              className={inputClass}
              aria-invalid={Boolean(fieldErrors.city)}
              aria-describedby={fieldErrors.city ? "checkout-city-error" : undefined}
            />
          </Field>
        </div>
        <Field id="checkout-address" label={t.form.address} error={errorText("address")}>
          <input
            id="checkout-address"
            name="address"
            autoComplete="street-address"
            value={values.address}
            onChange={(e) => setValue("address", e.target.value)}
            className={inputClass}
            aria-invalid={Boolean(fieldErrors.address)}
            aria-describedby={fieldErrors.address ? "checkout-address-error" : undefined}
          />
        </Field>
        <Field
          id="checkout-postal_code"
          label={t.form.postal_code}
          hint={t.form.postalHint}
          error={errorText("postal_code")}
        >
          <input
            id="checkout-postal_code"
            name="postal_code"
            autoComplete="postal-code"
            inputMode="numeric"
            dir="ltr"
            value={values.postal_code}
            onChange={(e) => setValue("postal_code", e.target.value)}
            className={`${inputClass} text-start`}
            aria-invalid={Boolean(fieldErrors.postal_code)}
            aria-describedby={fieldErrors.postal_code ? "checkout-postal_code-error" : undefined}
          />
        </Field>

        <p className="text-sm text-muted-foreground">{t.summary.paymentNote}</p>
        <button type="submit" disabled={submitting} className={`${primaryButton} w-full sm:w-auto`}>
          {submitting ? t.form.submitting : t.form.submit}
        </button>
      </form>

      <aside aria-labelledby="checkout-summary-title" className="order-1 h-fit rounded-lg border border-border p-4 lg:order-2">
        <h2 id="checkout-summary-title" className="text-lg font-semibold">
          {t.summary.title}
        </h2>
        {cart.has_issues && (
          <p role="status" className="mt-3 rounded-lg bg-muted px-3 py-2 text-sm">
            {t.summary.issues}
          </p>
        )}
        <ul className="mt-3 divide-y divide-border">
          {cart.items.map((item) => (
            <li key={item.id} className="py-3 text-sm">
              <p className="font-medium">{item.product.name}</p>
              <p className="text-muted-foreground">
                {item.color.name} · {item.variant_size.label}
              </p>
              <p className="mt-1 flex justify-between gap-2">
                <span>{fill(t.summary.quantity, { quantity: item.quantity })}</span>
                <span>{formatMoney(item.subtotal, locale)}</span>
              </p>
              {item.availability === "unavailable" && (
                <p className="mt-1 text-red-700 dark:text-red-400">{t.summary.unavailableLine}</p>
              )}
              {item.availability === "insufficient_stock" && (
                <p className="mt-1 text-red-700 dark:text-red-400">{t.summary.insufficientLine}</p>
              )}
            </li>
          ))}
        </ul>
        <p className="mt-3 flex justify-between border-t border-border pt-3 font-semibold">
          <span>{t.summary.itemsTotal}</span>
          <span data-testid="cart-total">{formatMoney(cart.total, locale)}</span>
        </p>
        <p className="mt-2 text-xs text-muted-foreground">{t.summary.shippingNote}</p>
      </aside>
    </div>
  );
}

function Notice({ title, body, children }: { title: string; body: string; children: ReactNode }) {
  return (
    <section className="mt-6 rounded-lg border border-border p-6">
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="mt-2 text-muted-foreground">{body}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error: string | null;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
        {hint && <span className="ms-2 font-normal text-muted-foreground">({hint})</span>}
      </label>
      {children}
      {error && (
        <p id={`${id}-error`} className="text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}

function Confirmation({
  order,
  locale,
  t,
  headingRef,
}: {
  order: Order;
  locale: Locale;
  t: CheckoutDictionary;
  headingRef: RefObject<HTMLHeadingElement | null>;
}) {
  const c = t.confirmation;
  const statusLabel = (c.statusLabels as Record<string, string>)[order.status] ?? order.status;
  const paymentLabel = (c.paymentLabels as Record<string, string>)[order.payment_status] ?? order.payment_status;
  return (
    <section className="mt-6 rounded-lg border border-border p-6" aria-labelledby="checkout-confirmation-title">
      <h2 id="checkout-confirmation-title" ref={headingRef} tabIndex={-1} className="text-2xl font-semibold">
        {c.title}
      </h2>
      <p className="mt-2 text-muted-foreground">{c.thanks}</p>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">{c.number}</dt>
          <dd data-testid="order-id" className="font-medium">
            {order.id}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{c.status}</dt>
          <dd>{statusLabel}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-muted-foreground">{c.payment}</dt>
          <dd>{paymentLabel}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-muted-foreground">{c.delivery}</dt>
          <dd>
            {order.recipient_name}
            <br />
            {order.province}، {order.city}
            <br />
            {order.address}
            <br />
            <span dir="ltr">{order.postal_code}</span>
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-muted-foreground">{c.phone}</dt>
          <dd dir="ltr" className="text-start">
            {order.customer_phone}
          </dd>
        </div>
      </dl>
      <h3 className="mt-6 font-semibold">{c.items}</h3>
      <ul className="mt-2 divide-y divide-border text-sm">
        {order.items.map((item) => (
          <li key={item.id} className="flex justify-between gap-3 py-2">
            <span>
              {item.product_name} · {item.color_name} · {item.size_label} × {item.quantity}
            </span>
            <span>{formatMoney(item.subtotal, locale)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 flex justify-between border-t border-border pt-3 font-semibold">
        <span>{c.total}</span>
        <span data-testid="order-total">{formatMoney(order.total, locale)}</span>
      </p>
      <p className="mt-2 text-xs text-muted-foreground">{t.summary.shippingNote}</p>
      <Link href={`/${locale}/products`} className={`${secondaryButton} mt-5`}>
        {c.continue}
      </Link>
    </section>
  );
}
