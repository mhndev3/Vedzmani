"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * Desktop uses a permanent, right-side filter card matching the original
 * catalog layout. Mobile keeps the modal drawer and its existing behavior.
 */
export function FilterDrawer({
  children,
  title,
  closeLabel,
  activeCount,
  openOnLoad = false,
}: {
  children: ReactNode;
  title: string;
  closeLabel: string;
  activeCount: number;
  openOnLoad?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    // Preserve the mobile drawer across filter navigation, never on desktop.
    if (
      openOnLoad &&
      dialog &&
      !dialog.open &&
      window.matchMedia("(max-width: 1023px)").matches
    ) {
      dialog.showModal();
    }
  }, [openOnLoad]);

  return (
    <>
      {/* Desktop: static sidebar, never a dialog or full-screen overlay. */}
      <div
        aria-label={title}
        className="hidden rounded-2xl border border-border bg-card p-4 text-foreground shadow-sm lg:block"
      >
        {children}
      </div>

      {/* Mobile: retain the existing modal drawer interaction. */}
      <button
        type="button"
        aria-haspopup="dialog"
        onClick={() => {
          const dialog = ref.current;
          if (dialog && !dialog.open) dialog.showModal();
        }}
        className="inline-flex h-10 items-center gap-2 rounded-full border border-border bg-background px-4 text-sm font-medium shadow-sm transition hover:-translate-y-0.5 hover:bg-muted lg:hidden"
      >
        {title}
        {activeCount > 0 && (
          <span className="rounded-full bg-primary px-2 text-xs text-primary-foreground">
            {activeCount}
          </span>
        )}
      </button>
      <dialog
        ref={ref}
        aria-label={title}
        onSubmit={() => ref.current?.close()}
        onClick={(e) => {
          if (e.target === ref.current) ref.current?.close();
        }}
        className="fixed inset-y-0 start-0 m-0 h-dvh max-h-dvh w-80 max-w-[88vw] overflow-y-auto rounded-e-3xl border border-border bg-background p-4 text-foreground shadow-2xl backdrop:bg-black/50 lg:hidden"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold">{title}</h2>
          <button
            type="button"
            onClick={() => ref.current?.close()}
            className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted"
          >
            {closeLabel}
          </button>
        </div>
        {children}
      </dialog>
    </>
  );
}
