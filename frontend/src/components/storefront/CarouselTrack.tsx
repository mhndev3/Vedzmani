"use client";

import { useRef, type ReactNode } from "react";

export function CarouselTrack({ children, itemCount }: { children: ReactNode; itemCount: number }) {
  const viewport = useRef<HTMLDivElement>(null);

  function scroll(direction: "previous" | "next") {
    const element = viewport.current;
    if (!element) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const distance = Math.max(220, Math.round(element.clientWidth * 0.82));
    element.scrollBy({
      left: direction === "next" ? -distance : distance,
      behavior: reducedMotion ? "auto" : "smooth",
    });
  }

  return (
    <>
      <div className="mb-3 flex justify-end gap-2">
        <button
          type="button"
          onClick={() => scroll("previous")}
          disabled={itemCount < 2}
          aria-label="محصولات قبلی"
          className="inline-flex size-10 items-center justify-center rounded-full border border-border bg-card shadow-sm transition hover:border-primary/40 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none">
            <path d="m14.5 5-7 7 7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <button
          type="button"
          onClick={() => scroll("next")}
          disabled={itemCount < 2}
          aria-label="محصولات بعدی"
          className="inline-flex size-10 items-center justify-center rounded-full border border-border bg-card shadow-sm transition hover:border-primary/40 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none">
            <path d="m9.5 5 7 7-7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
      <div
        ref={viewport}
        dir="rtl"
        className="overflow-x-auto overscroll-x-contain scroll-px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        <ul className="flex snap-x snap-mandatory gap-3 pb-3 sm:gap-4">
          {children}
        </ul>
      </div>
    </>
  );
}
