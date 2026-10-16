"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import type { Locale } from "@/i18n/config";
import { errorText } from "@/lib/browser-api";
import { cartApi } from "@/lib/cart";

export type AddToCartLabels = {
  sizes: string;
  sizeOutOfStock: string;
  addToCart: string;
  adding: string;
  added: string;
  viewCart: string;
  sizeRequired: string;
};

type Status =
  | { kind: "idle" }
  | { kind: "pending" }
  | { kind: "success" }
  | { kind: "error"; message: string };

/**
 * Size selection + add to cart. Stock shown here comes from the catalog response and is only a
 * usability hint: Django re-checks everything on POST /api/cart/items/ and its answer (success
 * or conflict) is what the customer is told. `size.id` is the VariantSize id the API expects.
 */
export function AddToCart({
  locale,
  sizes,
  labels,
  errors,
}: {
  locale: Locale;
  sizes: { id: number; label: string; in_stock: boolean }[];
  labels: AddToCartLabels;
  errors: Record<string, string>;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const inFlight = useRef(false);
  const anyInStock = sizes.some((s) => s.in_stock);
  const pending = status.kind === "pending";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    if (selected === null) {
      setStatus({ kind: "error", message: labels.sizeRequired });
      return;
    }
    inFlight.current = true;
    setStatus({ kind: "pending" });
    try {
      await cartApi.add(selected, 1);
      setStatus({ kind: "success" });
    } catch (e) {
      setStatus({ kind: "error", message: errorText(errors, e) });
    } finally {
      inFlight.current = false;
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <fieldset className="mt-6" disabled={pending}>
        <legend className="text-sm font-semibold">{labels.sizes}</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {sizes.map((size) => (
            <label key={size.id} className="relative">
              <input
                type="radio"
                name="size"
                value={size.id}
                className="peer sr-only"
                disabled={!size.in_stock}
                checked={selected === size.id}
                onChange={() => {
                  setSelected(size.id);
                  setStatus({ kind: "idle" });
                }}
              />
              <span className="inline-flex h-10 min-w-12 cursor-pointer items-center justify-center rounded-lg border border-border px-3 text-sm hover:bg-muted peer-checked:border-primary peer-checked:ring-1 peer-checked:ring-primary peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ring peer-disabled:cursor-not-allowed peer-disabled:text-muted-foreground peer-disabled:line-through peer-disabled:hover:bg-transparent">
                {size.label}
                {!size.in_stock && <span className="sr-only"> ({labels.sizeOutOfStock})</span>}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="mt-8">
        <button
          type="submit"
          disabled={!anyInStock || pending}
          aria-busy={pending}
          className="inline-flex h-12 w-full items-center justify-center rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
        >
          {pending ? labels.adding : labels.addToCart}
        </button>

        <div className="mt-3 min-h-5 text-sm" aria-live="polite">
          {status.kind === "success" && (
            <p role="status" className="flex flex-wrap items-center gap-x-3">
              <span>{labels.added}</span>
              <Link href={`/${locale}/cart`} className="font-medium underline underline-offset-4">
                {labels.viewCart}
              </Link>
            </p>
          )}
          {status.kind === "error" && (
            <p role="alert" className="font-medium">
              {status.message}
            </p>
          )}
        </div>
      </div>
    </form>
  );
}
