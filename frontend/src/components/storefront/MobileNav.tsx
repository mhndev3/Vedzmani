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
          <h2 className="mb-2 px-3 text-xs font-semibold text-muted-foreground">{labels.categories}</h2>
          <ul className="grid grid-cols-2 gap-1">
            {categories.map((item) => (
              <li key={item.href}>
                <Link href={item.href} onClick={close} className="block rounded-lg px-3 py-3 text-sm hover:bg-muted">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="my-3 border-t border-border" />
          <ul className="flex flex-col">
            {items.map((item) => (
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
