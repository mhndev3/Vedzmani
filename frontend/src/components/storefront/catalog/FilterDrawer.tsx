"use client";

import { useRef, type ReactNode } from "react";

/**
 * The only client code in the catalog. One <dialog> serves both layouts:
 * below `lg` it is a native modal sheet (focus trap, Esc and backdrop come
 * from the platform); from `lg` up it is displayed statically as the sidebar.
 * The filter form inside is server-rendered, so there is a single DOM copy.
 */
export function FilterDrawer({
  children,
  title,
  closeLabel,
  activeCount,
}: {
  children: ReactNode;
  title: string;
  closeLabel: string;
  activeCount: number;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  return (
    <>
      <button
        type="button"
        aria-haspopup="dialog"
        onClick={() => ref.current?.showModal()}
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
        className="fixed inset-y-0 start-0 m-0 h-dvh max-h-dvh w-80 max-w-[88vw] overflow-y-auto rounded-e-3xl border border-border bg-background p-4 text-foreground shadow-2xl backdrop:bg-black/50 lg:static lg:block lg:h-auto lg:max-h-none lg:w-full lg:max-w-none lg:overflow-visible lg:rounded-2xl lg:bg-card lg:p-4 lg:shadow-sm"
      >
        <div className="mb-4 flex items-center justify-between lg:hidden">
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
