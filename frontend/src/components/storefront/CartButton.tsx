"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import type { Locale } from "@/i18n/config";
import { cartApi } from "@/lib/cart";
import { BagIcon } from "./icons";

export function CartButton({ locale }: { locale: Locale }) {
  const [count, setCount] = useState(0);
  const pathname = usePathname();

  useEffect(() => {
    let active = true;
    // Ignore an older GET response if a cart mutation completed while it was in flight.
    let mutationVersion = 0;
    const refresh = () => {
      const requestedVersion = mutationVersion;
      cartApi.get()
        .then((cart) => {
          if (active && requestedVersion === mutationVersion) setCount(cart.item_count);
        })
        .catch(() => {
          if (active && requestedVersion === mutationVersion) setCount(0);
        });
    };
    const updated = (event: Event) => {
      const itemCount = (event as CustomEvent<{ itemCount: number }>).detail?.itemCount;
      if (Number.isFinite(itemCount)) {
        mutationVersion += 1;
        setCount(Math.max(0, itemCount));
      }
    };

    window.addEventListener("vedzmani:cart-updated", updated);
    refresh();
    return () => {
      active = false;
      window.removeEventListener("vedzmani:cart-updated", updated);
    };
  }, [pathname]);

  return (
    <Link
      href={`/${locale}/cart`}
      aria-label={count > 0 ? `سبد خرید، ${count} کالا` : "سبد خرید"}
      className="relative inline-flex size-9 items-center justify-center rounded-lg hover:bg-muted"
    >
      <BagIcon width={19} height={19} />
      {count > 0 && (
        <span className="absolute -end-0.5 -top-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold leading-none text-white">
          {count > 99 ? "۹۹+" : new Intl.NumberFormat("fa-IR", { useGrouping: false }).format(count)}
        </span>
      )}
    </Link>
  );
}
