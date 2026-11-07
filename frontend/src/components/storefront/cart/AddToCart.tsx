"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import type { Locale } from "@/i18n/config";
import { BrowserApiError, errorText } from "@/lib/browser-api";
import { cartApi } from "@/lib/cart";
import { addGuestCartItem, type GuestCartLine } from "@/lib/guest-cart";

export type AddToCartLabels = {
  sizes: string; sizeOutOfStock: string; addToCart: string; adding: string; added: string;
  viewCart: string; sizeRequired: string; sizeMeasurements: string; description: string;
};
type Status = { kind: "idle" } | { kind: "pending" } | { kind: "success" } | { kind: "error"; message: string };

export function AddToCart({
  locale, sizes, labels, errors, guestContext,
}: {
  locale: Locale;
  sizes: { id: number; sku: string; label: string; in_stock: boolean; stock_quantity: number;
    measurements: { name: string; value: string; unit: string }[]; description: string }[];
  labels: AddToCartLabels;
  errors: Record<string, string>;
  guestContext: Omit<GuestCartLine, "variant_size_id" | "variant_size" | "quantity" | "stock_quantity">;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const inFlight = useRef(false);
  const anyInStock = sizes.some((s) => s.stock_quantity > 0);
  const selectedSize = sizes.find((size) => size.id === selected) ?? null;
  const pending = status.kind === "pending";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    if (selectedSize === null) { setStatus({ kind: "error", message: labels.sizeRequired }); return; }
    inFlight.current = true;
    setStatus({ kind: "pending" });
    try {
      await cartApi.add(selectedSize.id, 1);
      setStatus({ kind: "success" });
    } catch (error) {
      if (error instanceof BrowserApiError && error.status === 401) {
        // Guest snapshots are display-only; Django rechecks catalog state and prices at merge time.
        addGuestCartItem({
          ...guestContext, variant_size_id: selectedSize.id,
          variant_size: { id: selectedSize.id, sku: selectedSize.sku, label: selectedSize.label },
          quantity: 1, stock_quantity: selectedSize.stock_quantity,
        });
        setStatus({ kind: "success" });
      } else setStatus({ kind: "error", message: errorText(errors, error) });
    } finally { inFlight.current = false; }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <fieldset className="mt-6" disabled={pending}>
        <legend className="text-sm font-semibold">{labels.sizes}</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {sizes.map((size) => (
            <label key={size.id} className="relative">
              <input type="radio" name="size" value={size.id} className="peer sr-only"
                disabled={size.stock_quantity === 0} aria-label={size.label} checked={selected === size.id}
                onChange={() => { setSelected(size.id); setStatus({ kind: "idle" }); }} />
              <span className={`inline-flex h-10 min-w-16 cursor-pointer items-center justify-center rounded-lg border px-3 text-sm transition-all duration-150 ease-out peer-checked:-translate-y-0.5 peer-checked:scale-[1.03] peer-checked:shadow-sm peer-checked:border-primary peer-checked:ring-1 peer-checked:ring-primary peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ring peer-disabled:cursor-not-allowed peer-disabled:hover:bg-transparent ${size.stock_quantity === 0 ? "border-red-500 text-red-600 dark:border-red-400 dark:text-red-400" : "border-border hover:bg-muted"}`}>
                <span dir="ltr" className="whitespace-nowrap">{size.label} : {size.stock_quantity}</span>
                {size.stock_quantity === 0 && <span className="sr-only"> ({labels.sizeOutOfStock})</span>}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {selectedSize?.description.trim() && (
        <section className="mt-6" aria-live="polite" aria-atomic="true">
          <h2 className="mb-2 text-sm font-semibold">{labels.description}</h2>
          <p className="whitespace-pre-line text-sm leading-7 text-muted-foreground">{selectedSize.description}</p>
        </section>
      )}
      {selectedSize && selectedSize.measurements.length > 0 && (
        <section className="mt-6" aria-live="polite" aria-atomic="true">
          <h2 className="mb-2 text-sm font-semibold">{labels.sizeMeasurements.replace("{size}", selectedSize.label)}</h2>
          <table className="w-full border-collapse overflow-hidden rounded-lg text-sm" aria-label={labels.sizeMeasurements.replace("{size}", selectedSize.label)}>
            <tbody>{selectedSize.measurements.map((measurement, index) => (
              <tr key={`${selectedSize.id}-${index}`} className="border-b border-border last:border-0">
                <th scope="row" className="w-1/2 bg-muted/60 px-3 py-2 text-start font-medium">{measurement.name}</th>
                <td dir="ltr" className="px-3 py-2 text-start">{measurement.value}{measurement.unit ? ` ${measurement.unit}` : ""}</td>
              </tr>
            ))}</tbody>
          </table>
        </section>
      )}
      <div className="mt-8">
        <button type="submit" disabled={!anyInStock || pending} aria-busy={pending}
          className="inline-flex h-12 w-full items-center justify-center rounded-xl bg-primary px-6 text-sm font-medium text-primary-foreground transition-transform duration-150 hover:-translate-y-0.5 active:scale-[0.99] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto">
          {pending ? labels.adding : labels.addToCart}
        </button>
        <div className="mt-3 min-h-5 text-sm" aria-live="polite">
          {status.kind === "success" && <p role="status" className="flex flex-wrap items-center gap-x-3">
            <span>{labels.added}</span><Link href={`/${locale}/cart`} className="font-medium underline underline-offset-4">{labels.viewCart}</Link>
          </p>}
          {status.kind === "error" && <p role="alert" className="font-medium">{status.message}</p>}
        </div>
      </div>
    </form>
  );
}
