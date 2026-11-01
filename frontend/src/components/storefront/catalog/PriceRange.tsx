"use client";

import { useState } from "react";

const MAX_PRICE = 50_000_000;
const STEP = 50_000;

export function PriceRange({ min, max }: { min: string; max: string }) {
  const [minValue, setMinValue] = useState(min ? Number(min) : 0);
  const [maxValue, setMaxValue] = useState(max ? Number(max) : MAX_PRICE);
  const [minActive, setMinActive] = useState(Boolean(min));
  const [maxActive, setMaxActive] = useState(Boolean(max));
  const format = (value: number) => new Intl.NumberFormat("fa-IR").format(value);

  return (
    <fieldset className="min-w-0 border-t border-border pt-4">
      <legend className="mb-3 text-sm font-semibold">محدوده قیمت (تومان)</legend>
      <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>ارزان‌ترین: {format(minValue)}</span>
        <span>گران‌ترین: {format(maxValue)}</span>
      </div>
      <label className="mt-3 block text-xs text-muted-foreground" htmlFor="catalog-min-price-range">حداقل قیمت</label>
      <input id="catalog-min-price-range" type="range" min={0} max={MAX_PRICE} step={STEP} value={minValue}
        onChange={(event) => { const next = Number(event.target.value); setMinValue(Math.min(next, maxValue)); setMinActive(true); }}
        className="mt-1 w-full cursor-pointer accent-[var(--primary)]" />
      <label className="mt-3 block text-xs text-muted-foreground" htmlFor="catalog-max-price-range">حداکثر قیمت</label>
      <input id="catalog-max-price-range" type="range" min={0} max={MAX_PRICE} step={STEP} value={maxValue}
        onChange={(event) => { const next = Number(event.target.value); setMaxValue(Math.max(next, minValue)); setMaxActive(true); }}
        className="mt-1 w-full cursor-pointer accent-[var(--primary)]" />
      <div className="mt-2 flex justify-between text-[11px] text-muted-foreground"><span>۰</span><span>{format(MAX_PRICE)} تومان</span></div>
      <input type="hidden" name="min_price" value={minActive ? String(minValue) : ""} />
      <input type="hidden" name="max_price" value={maxActive ? String(maxValue) : ""} />
      <button type="button" onClick={() => { setMinValue(0); setMaxValue(MAX_PRICE); setMinActive(false); setMaxActive(false); }}
        className="mt-2 text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground">پاک کردن محدوده قیمت</button>
    </fieldset>
  );
}
