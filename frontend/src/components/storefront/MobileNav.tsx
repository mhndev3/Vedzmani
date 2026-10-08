"use client";

import { useRef } from "react";
import Link from "next/link";
import { CloseIcon, MenuIcon } from "./icons";

type Props = {
  items: { href: string; label: string }[];
  labels: { open: string; close: string; title: string };
};

/**
 * Uses the native modal <dialog>: built-in focus trap, Escape to close,
 * inert background and focus return, with almost no JS. Placed at the
 * inline-start edge with logical margins, so it is correct in RTL and LTR.
 */
export function MobileNav({ items, labels }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const close = () => ref.current?.close();

  return (
    <>
      <button
        type="button"
        aria-haspopup="dialog"
        aria-label={labels.open}
        onClick={() => ref.current?.showModal()}
        className="inline-flex size-10 items-center justify-center rounded-lg hover:bg-muted lg:hidden"
      >
        <MenuIcon />
      </button>
      <dialog
        ref={ref}
        aria-label={labels.title}
        onClick={(e) => {
          if (e.target === e.currentTarget) close();
        }}
        className="mt-0 mb-0 ms-0 me-auto h-dvh max-h-none w-72 max-w-[85vw] border-e border-border bg-background p-0 text-foreground backdrop:bg-black/50 lg:hidden"
      >
        <div className="flex items-center justify-between border-b border-border p-3 ps-4">
          <span className="font-semibold">{labels.title}</span>
          <button
            type="button"
            aria-label={labels.close}
            onClick={close}
            className="inline-flex size-10 items-center justify-center rounded-lg hover:bg-muted"
          >
            <CloseIcon />
          </button>
        </div>
        <nav aria-label={labels.title} className="p-2">
          <ul className="flex flex-col">
            {items.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={close}
                  className="block rounded-lg px-3 py-3 hover:bg-muted"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </dialog>
    </>
  );
}
