"use client";

import { useRef } from "react";
import Link from "next/link";
import { CloseIcon, MenuIcon } from "./icons";

type MenuLink = { href: string; label: string };
type Props = {
  items: MenuLink[];
  categories: MenuLink[];
  labels: { open: string; close: string; title: string; categories: string };
};

export function MobileNav({ items, categories, labels }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const close = () => ref.current?.close();

  return (
    <>
      <button
        type="button"
        aria-haspopup="dialog"
        aria-label={labels.open}
        onClick={() => ref.current?.showModal()}
        className="inline-flex size-9 items-center justify-center rounded-lg hover:bg-muted"
      >
        <MenuIcon />
      </button>
      <dialog
        ref={ref}
        aria-label={labels.title}
        onClick={(event) => {
          if (event.target === event.currentTarget) close();
        }}
        className="mt-0 mb-0 ms-0 me-auto h-dvh max-h-none w-80 max-w-[88vw] border-e border-border bg-background p-0 text-foreground backdrop:bg-black/50"
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
        <nav aria-label={labels.title} className="max-h-[calc(100dvh-4.5rem)] overflow-y-auto p-3">
          <ul className="flex flex-col">
            <li>
              <Link href={items[0].href} onClick={close} className="block rounded-lg px-3 py-3 hover:bg-muted">
                {items[0].label}
              </Link>
            </li>
          </ul>
          <details className="group">
            <summary className="flex cursor-pointer list-none items-center justify-between rounded-lg px-3 py-3 text-sm font-semibold hover:bg-muted [&::-webkit-details-marker]:hidden">
              {labels.categories}
              <svg
                aria-hidden="true"
                viewBox="0 0 16 16"
                className="size-3.5 transition-transform duration-200 ease-out group-open:rotate-90 motion-reduce:transition-none"
                fill="none"
              >
                <path d="M6 3.5 10.5 8 6 12.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </summary>
            <ul className="grid grid-cols-2 gap-1 px-1 pb-2">
              {categories.map((item) => (
                <li key={item.href}>
                  <Link href={item.href} onClick={close} className="block rounded-lg px-3 py-3 text-sm hover:bg-muted">
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </details>
          <div className="my-3 border-t border-border" />
          <ul className="flex flex-col">
            {items.slice(1).map((item) => (
              <li key={item.href}>
                <Link href={item.href} onClick={close} className="block rounded-lg px-3 py-3 hover:bg-muted">
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
