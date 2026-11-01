"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries/fa";
import { BrowserApiError, errorText } from "@/lib/browser-api";
import { cartApi, type Cart, type CartItem } from "@/lib/cart";
import {
  readGuestCart, removeGuestCartItem, setGuestCartQuantity, type GuestCartLine,
} from "@/lib/guest-cart";
import { fill, formatCurrency, formatPrice } from "@/lib/format";
import { signInHref } from "@/lib/auth/redirect";

type State =
  | { kind: "loading" }
  | { kind: "anonymous" }
  | { kind: "error" }
  | { kind: "guest"; items: GuestCartLine[] }
  | { kind: "ready"; cart: Cart };

const buttonBase =
  "inline-flex items-center justify-center rounded-lg border border-border text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50";

export function CartView({ locale, t }: { locale: Locale; t: Dictionary["cart"] }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inFlight = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let cancelled = false;
    cartApi.get().then((cart) => {
      if (!cancelled) setState({ kind: "ready", cart });
    }).catch((e: unknown) => {
      if (cancelled) return;
      if (e instanceof BrowserApiError && e.status === 401) {
        const guest = readGuestCart().items;
        setState(guest.length ? { kind: "guest", items: guest } : { kind: "anonymous" });
      } else setState({ kind: "error" });
    });
    return () => { cancelled = true; };
  }, [attempt]);

  function retry() {
    setState({ kind: "loading" });
    setAttempt((n) => n + 1);
  }

  async function run(action: () => Promise<Cart>, moveFocus = false) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const cart = await action();
      setState({ kind: "ready", cart });
      setNotice(t.updated);
      if (moveFocus) heading.current?.focus();
    } catch (e) {
      if (e instanceof BrowserApiError && e.status === 401) {
        const guest = readGuestCart().items;
        setState(guest.length ? { kind: "guest", items: guest } : { kind: "anonymous" });
      } else {
        setError(errorText(t.errors, e));
        if (e instanceof BrowserApiError && (e.status === 400 || e.status === 409)) {
          try { setState({ kind: "ready", cart: await cartApi.get() }); } catch { /* keep current view */ }
        }
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function updateGuest(items: GuestCartLine[]) {
    setState(items.length ? { kind: "guest", items } : { kind: "anonymous" });
    setNotice(t.updated);
  }

  const checkoutLink = `/${locale}/checkout`;

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-10">
      <h1 ref={heading} tabIndex={-1} className="text-2xl font-semibold outline-none sm:text-3xl">{t.title}</h1>
      <div className="mt-6" aria-live="polite">
        {notice && <p role="status" className="sr-only">{notice}</p>}
        {error && <p role="alert" className="mb-4 rounded-lg border border-border p-3 text-sm font-medium">{error}</p>}
      </div>

      {state.kind === "loading" && (
        <div role="status" aria-busy="true" className="space-y-4">
          <span className="sr-only">{t.loading}</span>
          {[0, 1].map((i) => <div key={i} aria-hidden className="flex gap-4">
            <div className="aspect-[3/4] w-20 shrink-0 rounded-lg bg-muted" />
            <div className="flex-1 space-y-2"><div className="h-4 w-1/2 rounded bg-muted" /><div className="h-4 w-1/3 rounded bg-muted" /></div>
          </div>)}
        </div>
      )}

      {state.kind === "anonymous" && (
        <section className="rounded-lg border border-border p-6">
          <h2 className="text-lg font-semibold">{t.emptyTitle}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{t.emptyText}</p>
          <Link href={`/${locale}/products`} className="mt-4 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground">{t.browse}</Link>
        </section>
      )}

      {state.kind === "error" && (
        <section role="alert" className="rounded-lg border border-border p-6">
          <h2 className="text-lg font-semibold">{t.errorTitle}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{t.errorText}</p>
          <button type="button" onClick={retry} className={`${buttonBase} mt-4 h-10 px-4 font-medium`}>{t.retry}</button>
        </section>
      )}

      {state.kind === "ready" && state.cart.items.length === 0 && (
        <section className="rounded-lg border border-border p-6">
          <h2 className="text-lg font-semibold">{t.emptyTitle}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{t.emptyText}</p>
          <Link href={`/${locale}/products`} className="mt-4 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground">{t.browse}</Link>
        </section>
      )}

      {state.kind === "guest" && state.items.length > 0 && (
        <>
          <ul className="divide-y divide-border border-y border-border">
            {state.items.map((item) => (
              <GuestCartLineView key={item.variant_size_id} item={item} locale={locale} t={t}
                onQuantity={(quantity) => updateGuest(setGuestCartQuantity(item.variant_size_id, quantity))}
                onRemove={() => updateGuest(removeGuestCartItem(item.variant_size_id))} />
            ))}
          </ul>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
            <p className="text-lg font-semibold">
              <span>{t.total}</span>{" "}
              <span>{formatCurrency(state.items.reduce((sum, item) => sum + Number(item.unit_price) * item.quantity, 0), locale)}</span>
            </p>
            <Link href={signInHref(locale, checkoutLink)} className="inline-flex h-12 items-center rounded-xl bg-primary px-6 text-sm font-medium text-primary-foreground transition-transform duration-150 hover:-translate-y-0.5 active:scale-[0.99]">
              {t.checkout}
            </Link>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">{t.guestNote}</p>
          <p className="mt-2 text-xs text-muted-foreground">{t.orderDisabledNote}</p>
        </>
      )}

      {state.kind === "ready" && state.cart.items.length > 0 && (
        <>
          <ul className="divide-y divide-border border-y border-border">
            {state.cart.items.map((item) => <CartLine key={item.id} item={item} locale={locale} t={t} busy={busy} run={run} />)}
          </ul>
          {state.cart.has_issues && <p className="mt-4 text-sm font-medium">{t.issuesNote}</p>}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
            <p className="text-lg font-semibold"><span>{t.total}</span>{" "}<span data-testid="cart-total">{formatCurrency(state.cart.total, locale)}</span></p>
            {state.cart.has_issues ? (
              <span aria-disabled="true" className="inline-flex h-12 cursor-not-allowed items-center rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground opacity-50">{t.checkout}</span>
            ) : (
              <Link href={checkoutLink} className="inline-flex h-12 items-center rounded-xl bg-primary px-6 text-sm font-medium text-primary-foreground transition-transform duration-150 hover:-translate-y-0.5 active:scale-[0.99] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">{t.checkout}</Link>
            )}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">{t.orderDisabledNote}</p>
        </>
      )}
    </div>
  );
}

function GuestCartLineView({
  item, locale, t, onQuantity, onRemove,
}: {
  item: GuestCartLine; locale: Locale; t: Dictionary["cart"];
  onQuantity: (quantity: number) => void; onRemove: () => void;
}) {
  const name = item.product.name;
  return (
    <li className="flex gap-4 py-5" data-testid="guest-cart-line">
      <div className="relative aspect-[3/4] w-20 shrink-0 overflow-hidden rounded-lg bg-muted sm:w-24">
        {item.image && <Image src={item.image.thumbnail_url || item.image.url} alt={item.image.alt_text || name}
          fill sizes="96px" loading="lazy" unoptimized className="object-cover" />}
      </div>
      <div className="min-w-0 flex-1">
        <Link href={`/${locale}/products/${item.product.slug}?color=${item.color.slug}`} className="font-medium hover:underline">{name}</Link>
        <p className="mt-1 text-sm text-muted-foreground">{t.colorLabel}: {item.color.name} · {t.sizeLabel}: {item.variant_size.label}</p>
        <p className="mt-1 text-sm">{t.unitPrice}: {formatCurrency(item.unit_price, locale)}</p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <div className="inline-flex items-center gap-2" role="group" aria-label={`${t.quantity}: ${name}`}>
            <button type="button" className={`${buttonBase} h-9 w-9`} aria-label={fill(t.decrease, { name })}
              disabled={item.quantity <= 1} onClick={() => onQuantity(item.quantity - 1)}>−</button>
            <output className="min-w-6 text-center text-sm" aria-label={t.quantity}>{formatPrice(item.quantity, locale)}</output>
            <button type="button" className={`${buttonBase} h-9 w-9`} aria-label={fill(t.increase, { name })}
              onClick={() => onQuantity(item.quantity + 1)}>+</button>
          </div>
          <button type="button" className={`${buttonBase} h-9 px-3`} aria-label={fill(t.removeItem, { name })} onClick={onRemove}>{t.remove}</button>
        </div>
      </div>
      <p className="shrink-0 text-sm font-medium">{formatCurrency(Number(item.unit_price) * item.quantity, locale)}</p>
    </li>
  );
}

function CartLine({
  item, locale, t, busy, run,
}: {
  item: CartItem; locale: Locale; t: Dictionary["cart"]; busy: boolean;
  run: (action: () => Promise<Cart>, moveFocus?: boolean) => Promise<void>;
}) {
  const name = item.product.name;
  const unavailable = item.availability === "unavailable";
  return (
    <li className="flex gap-4 py-5" data-testid="cart-line">
      <div className="relative aspect-[3/4] w-20 shrink-0 overflow-hidden rounded-lg bg-muted sm:w-24">
        {item.image && <Image src={item.image.thumbnail_url || item.image.url} alt={item.image.alt_text || name}
          fill sizes="96px" loading="lazy" unoptimized className="object-cover" />}
      </div>
      <div className="min-w-0 flex-1">
        <Link href={`/${locale}/products/${item.product.slug}?color=${item.color.slug}`} className="font-medium hover:underline">{name}</Link>
        <p className="mt-1 text-sm text-muted-foreground">{t.colorLabel}: {item.color.name} · {t.sizeLabel}: {item.variant_size.label}</p>
        <p className="mt-1 text-sm">{t.unitPrice}: {formatCurrency(item.unit_price, locale)}</p>
        {item.availability === "insufficient_stock" && <p className="mt-2 text-sm font-medium">{t.insufficientStock}</p>}
        {unavailable && <p className="mt-2 text-sm font-medium">{t.unavailable}</p>}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <div className="inline-flex items-center gap-2" role="group" aria-label={`${t.quantity}: ${name}`}>
            <button type="button" className={`${buttonBase} h-9 w-9`} aria-label={fill(t.decrease, { name })}
              disabled={busy || unavailable || item.quantity <= 1} onClick={() => run(() => cartApi.setQuantity(item.id, item.quantity - 1))}>−</button>
            <output className="min-w-6 text-center text-sm" aria-label={t.quantity} data-testid="cart-quantity">{formatPrice(item.quantity, locale)}</output>
            <button type="button" className={`${buttonBase} h-9 w-9`} aria-label={fill(t.increase, { name })}
              disabled={busy || unavailable} onClick={() => run(() => cartApi.setQuantity(item.id, item.quantity + 1))}>+</button>
          </div>
          <button type="button" className={`${buttonBase} h-9 px-3`} aria-label={fill(t.removeItem, { name })}
            disabled={busy} onClick={() => run(() => cartApi.remove(item.id), true)}>{t.remove}</button>
        </div>
      </div>
      <p className="shrink-0 text-sm font-medium" aria-label={t.subtotal}>{formatCurrency(item.subtotal, locale)}</p>
    </li>
  );
}
