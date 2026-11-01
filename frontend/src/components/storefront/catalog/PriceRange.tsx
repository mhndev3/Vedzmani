"use client";

import { useState } from "react";

const MAX_PRICE = 50_000_000;
const STEP = 500;

export function PriceRange({ min, max }: { min: string; max: string }) {
  const [minValue, setMinValue] = useState(min ? Math.min(MAX_PRICE, Number(min)) : 0);
  const [maxValue, setMaxValue] = useState(max ? Math.min(MAX_PRICE, Number(max)) : MAX_PRICE);
  const [minActive, setMinActive] = useState(Boolean(min));
  const [maxActive, setMaxActive] = useState(Boolean(max));
  const format = (value: number) => new Intl.NumberFormat("fa-IR").format(value);
  const minPercent = (minValue / MAX_PRICE) * 100;
  const maxPercent = (maxValue / MAX_PRICE) * 100;

  return (
    <fieldset className="min-w-0 border-t border-border pt-4">
      <legend className="mb-3 text-sm font-semibold">محدوده قیمت (تومان)</legend>
      <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>ارزان‌ترین: {format(minValue)}</span>
        <span>گران‌ترین: {format(maxValue)}</span>
      </div>
      <div data-testid="price-range-control" dir="ltr" className="relative mt-4 h-8">
        <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-muted" />
        <div
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-primary"
          style={{ left: minPercent + "%", width: Math.max(0, maxPercent - minPercent) + "%" }}
        />
        <input
          aria-label="حداقل قیمت"
          type="range"
          min={0}
          max={Math.max(0, maxValue - STEP)}
          step={STEP}
          value={minValue}
          onChange={(event) => { const next = Number(event.target.value); setMinValue(Math.min(next, maxValue - STEP)); setMinActive(true); }}
          className="price-range-thumb pointer-events-none absolute inset-0 z-20 h-8 w-full cursor-pointer appearance-none bg-transparent"
        />
        <input
          aria-label="حداکثر قیمت"
          type="range"
          min={Math.min(MAX_PRICE, minValue + STEP)}
          max={MAX_PRICE}
          step={STEP}
          value={maxValue}
          onChange={(event) => { const next = Number(event.target.value); setMaxValue(Math.max(next, minValue + STEP)); setMaxActive(true); }}
          className="price-range-thumb pointer-events-none absolute inset-0 z-30 h-8 w-full cursor-pointer appearance-none bg-transparent"
        />
      </div>
      <div className="flex justify-between text-[11px] text-muted-foreground">
        <span>۰</span><span>{format(MAX_PRICE)} تومان</span>
      </div>
      <input type="hidden" name="min_price" value={minActive ? String(minValue) : ""} />
      <input type="hidden" name="max_price" value={maxActive ? String(maxValue) : ""} />
      <button type="button" onClick={() => { setMinValue(0); setMaxValue(MAX_PRICE); setMinActive(false); setMaxActive(false); }}
        className="mt-2 text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground">پاک کردن محدوده قیمت</button>
    </fieldset>
  );
}
