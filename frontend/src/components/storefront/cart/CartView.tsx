"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries/fa";
import { BrowserApiError, errorText } from "@/lib/browser-api";
import { cartApi, type Cart, type CartItem } from "@/lib/cart";
import { fill, formatPrice } from "@/lib/format";

type State =
  | { kind: "loading" }
  | { kind: "anonymous" }
  | { kind: "error" }
  | { kind: "ready"; cart: Cart };

const buttonBase =
  "inline-flex items-center justify-center rounded-lg border border-border text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50";

/**
 * Cart page body. Items, quantities, unit prices, subtotals, total and availability are rendered
 * exactly as Django returns them (backend/CART.md); every change goes through the cart API and the
 * response replaces the whole cart. Nothing is computed or cached on the client.
 */
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
    cartApi
      .get()
      .then((cart) => {
        if (!cancelled) setState({ kind: "ready", cart });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setState(e instanceof BrowserApiError && e.status === 401 ? { kind: "anonymous" } : { kind: "error" });
      });
    return () => {
      cancelled = true;
    };
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
        setState({ kind: "anonymous" });
      } else {
        setError(errorText(t.errors, e));
        if (e instanceof BrowserApiError && (e.status === 400 || e.status === 409)) {
          // The server refused: show its current truth rather than our stale copy.
          try {
            setState({ kind: "ready", cart: await cartApi.get() });
          } catch {
            /* keep what is on screen; the error above already tells the customer */
          }
        }
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6">
      <h1 ref={heading} tabIndex={-1} className="text-2xl font-semibold outline-none sm:text-3xl">
        {t.title}
      </h1>

      <div className="mt-6" aria-live="polite">
        {notice && (
          <p role="status" className="sr-only">
            {notice}
          </p>
        )}
        {error && (
          <p role="alert" className="mb-4 rounded-lg border border-border p-3 text-sm font-medium">
            {error}
          </p>
        )}
      </div>

      {state.kind === "loading" && (
        <div role="status" aria-busy="true" className="space-y-4">
          <span className="sr-only">{t.loading}</span>
          {[0, 1].map((i) => (
            <div key={i} aria-hidden className="flex gap-4">
              <div className="aspect-[3/4] w-20 shrink-0 rounded-lg bg-muted" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-1/2 rounded bg-muted" />
                <div className="h-4 w-1/3 rounded bg-muted" />
              </div>
            </div>
          ))}
        </div>
      )}

      {state.kind === "anonymous" && (
        <section className="rounded-lg border border-border p-6">
          <h2 className="text-lg font-semibold">{t.signInTitle}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{t.signInText}</p>
        </section>
      )}

      {state.kind === "error" && (
        <section role="alert" className="rounded-lg border border-border p-6">
          <h2 className="text-lg font-semibold">{t.errorTitle}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{t.errorText}</p>
          <button type="button" onClick={retry} className={`${buttonBase} mt-4 h-10 px-4 font-medium`}>
            {t.retry}
          </button>
        </section>
      )}

      {state.kind === "ready" && state.cart.items.length === 0 && (
        <section className="rounded-lg border border-border p-6">
          <h2 className="text-lg font-semibold">{t.emptyTitle}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{t.emptyText}</p>
          <Link
            href={`/${locale}/products`}
            className="mt-4 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground"
          >
            {t.browse}
          </Link>
        </section>
      )}

      {state.kind === "ready" && state.cart.items.length > 0 && (
        <>
          <ul className="divide-y divide-border border-y border-border">
            {state.cart.items.map((item) => (
              <CartLine key={item.id} item={item} locale={locale} t={t} busy={busy} run={run} />
            ))}
          </ul>

          {state.cart.has_issues && (
            <p className="mt-4 text-sm font-medium">{t.issuesNote}</p>
          )}

          <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
            <p className="text-lg font-semibold">
              <span>{t.total}</span>{" "}
              <span data-testid="cart-total">{formatPrice(state.cart.total, locale)}</span>
            </p>
            {state.cart.has_issues ? (
              <span
                aria-disabled="true"
                className="inline-flex h-12 cursor-not-allowed items-center rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground opacity-50"
              >
                {t.checkout}
              </span>
            ) : (
              <Link
                href={`/${locale}/checkout`}
                className="inline-flex h-12 items-center rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              >
                {t.checkout}
              </Link>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function CartLine({
  item,
  locale,
  t,
  busy,
  run,
}: {
  item: CartItem;
  locale: Locale;
  t: Dictionary["cart"];
  busy: boolean;
  run: (action: () => Promise<Cart>, moveFocus?: boolean) => Promise<void>;
}) {
  const name = item.product.name;
  const unavailable = item.availability === "unavailable";

  return (
    <li className="flex gap-4 py-5" data-testid="cart-line">
      <div className="relative aspect-[3/4] w-20 shrink-0 overflow-hidden rounded-lg bg-muted sm:w-24">
        {item.image && (
          <Image
            src={item.image.url}
            alt={item.image.alt_text || name}
            fill
            sizes="96px"
            unoptimized
            className="object-cover"
          />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <Link
          href={`/${locale}/products/${item.product.slug}?color=${item.color.slug}`}
          className="font-medium hover:underline"
        >
          {name}
        </Link>
        <p className="mt-1 text-sm text-muted-foreground">
          {t.colorLabel}: {item.color.name} · {t.sizeLabel}: {item.variant_size.label}
        </p>
        <p className="mt-1 text-sm">
          {t.unitPrice}: {formatPrice(item.unit_price, locale)}
        </p>

        {item.availability === "insufficient_stock" && (
          <p className="mt-2 text-sm font-medium">{t.insufficientStock}</p>
        )}
        {unavailable && <p className="mt-2 text-sm font-medium">{t.unavailable}</p>}

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <div className="inline-flex items-center gap-2" role="group" aria-label={`${t.quantity}: ${name}`}>
            <button
              type="button"
              className={`${buttonBase} h-9 w-9`}
              aria-label={fill(t.decrease, { name })}
              disabled={busy || unavailable || item.quantity <= 1}
              onClick={() => run(() => cartApi.setQuantity(item.id, item.quantity - 1))}
            >
              −
            </button>
            <output className="min-w-6 text-center text-sm" aria-label={t.quantity} data-testid="cart-quantity">
              {formatPrice(item.quantity, locale)}
            </output>
            <button
              type="button"
              className={`${buttonBase} h-9 w-9`}
              aria-label={fill(t.increase, { name })}
              disabled={busy || unavailable}
              onClick={() => run(() => cartApi.setQuantity(item.id, item.quantity + 1))}
            >
              +
            </button>
          </div>
          <button
            type="button"
            className={`${buttonBase} h-9 px-3`}
            aria-label={fill(t.removeItem, { name })}
            disabled={busy}
            onClick={() => run(() => cartApi.remove(item.id), true)}
          >
            {t.remove}
          </button>
        </div>
      </div>

      <p className="shrink-0 text-sm font-medium" aria-label={t.subtotal}>
        {formatPrice(item.subtotal, locale)}
      </p>
    </li>
  );
}
