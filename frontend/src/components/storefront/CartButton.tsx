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
    const refresh = () => {
      cartApi.get().then((cart) => { if (active) setCount(cart.item_count); })
        .catch(() => { if (active) setCount(0); });
    };
    const updated = (event: Event) => {
      const itemCount = (event as CustomEvent<{ itemCount: number }>).detail?.itemCount;
      if (Number.isFinite(itemCount)) setCount(Math.max(0, itemCount));
    };
    refresh();
    window.addEventListener("vedzmani:cart-updated", updated);
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
