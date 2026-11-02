"use client";

import {
  Children,
  cloneElement,
  isValidElement,
  useEffect,
  useRef,
  type ReactElement,
  type ReactNode,
} from "react";

export function CarouselTrack({ children, itemCount }: { children: ReactNode; itemCount: number }) {
  const viewport = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLUListElement>(null);
  const resumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function scroll(direction: "previous" | "next") {
    const element = viewport.current;
    if (!element) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const distance = Math.max(220, Math.round(element.clientWidth * 0.82));
    element.scrollBy({
      left: direction === "next" ? -distance : distance,
      behavior: reducedMotion ? "auto" : "smooth",
    });
    pauseAndResumeAfterInteraction();
  }

  function pauseAndResumeAfterInteraction() {
    if (resumeTimer.current) clearTimeout(resumeTimer.current);
    resumeTimer.current = setTimeout(() => {
      resumeTimer.current = null;
      paused.current = false;
      lastFrame.current = 0;
    }, 6000);
    paused.current = true;
  }

  const paused = useRef(false);
  const lastFrame = useRef(0);

  useEffect(() => {
    const element = viewport.current;
    const list = track.current;
    if (!element || !list || itemCount < 2) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (reduceMotion.matches) return;

    let frame = 0;
    let visible = true;

    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      lastFrame.current = 0;
    }, { threshold: 0.05 });
    observer.observe(element);

    const animate = (now: number) => {
      if (!paused.current && visible && document.visibilityState === "visible") {
        const delta = lastFrame.current ? Math.min(now - lastFrame.current, 50) : 0;
        const first = list.children[0] as HTMLElement | undefined;
        const firstClone = list.children[itemCount] as HTMLElement | undefined;
        const loopDistance = first && firstClone
          ? Math.abs(first.offsetLeft - firstClone.offsetLeft)
          : 0;

        if (delta > 0 && loopDistance > element.clientWidth + 2) {
          // 100px per second: clearly visible while remaining smooth.
          element.scrollLeft -= delta * 0.1;
          if (element.scrollLeft <= -loopDistance) {
            element.scrollLeft += loopDistance;
          }
        }
      }

      lastFrame.current = now;
      frame = window.requestAnimationFrame(animate);
    };

    frame = window.requestAnimationFrame(animate);
    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      if (resumeTimer.current) clearTimeout(resumeTimer.current);
    };
  }, [itemCount]);

  const duplicateChildren = Children.map(children, (child, index) =>
    isValidElement(child)
      ? cloneElement(child as ReactElement<Record<string, unknown>>, {
          key: `infinite-copy-${index}`,
          "aria-hidden": true,
          inert: true,
        })
      : child,
  );

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
            <path d="m9.5 5 7 7-7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
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
            <path d="m14.5 5-7 7 7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
      <div
        className="relative w-full min-w-0 max-w-full overflow-x-hidden [contain:paint]"
        onMouseEnter={() => { paused.current = true; if (resumeTimer.current) clearTimeout(resumeTimer.current); }}
        onMouseLeave={pauseAndResumeAfterInteraction}
        onTouchStart={() => { paused.current = true; if (resumeTimer.current) clearTimeout(resumeTimer.current); }}
        onTouchEnd={pauseAndResumeAfterInteraction}
        onTouchCancel={pauseAndResumeAfterInteraction}
        onFocusCapture={() => { paused.current = true; if (resumeTimer.current) clearTimeout(resumeTimer.current); }}
        onBlurCapture={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            pauseAndResumeAfterInteraction();
          }
        }}
      >
        <div
          ref={viewport}
          dir="rtl"
          aria-label="جدیدترین محصولات"
          className="w-full min-w-0 max-w-full overflow-x-auto overflow-y-hidden overscroll-x-contain scroll-px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          <ul ref={track} className="flex w-full min-w-0 snap-x snap-mandatory gap-3 pb-3 sm:gap-4">
            {children}
            {duplicateChildren}
          </ul>
        </div>
      </div>
    </>
  );
}
