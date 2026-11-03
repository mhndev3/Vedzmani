"use client";

import { useRouter } from "next/navigation";
import type { ChangeEvent, ReactNode } from "react";

/**
 * A category selection is a facet-preview step, not an applied product filter.
 * Navigate with a draft URL instead of mutating React-owned form nodes. The
 * applied URL state is carried in applied_* fields so results remain unchanged.
 */
export function CategoryFilterAutoSubmit({ children }: { children: ReactNode }) {
  const router = useRouter();

  function handleChange(event: ChangeEvent<HTMLDivElement>) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || target.name !== "category" || target.type !== "checkbox") return;

    const form = target.form;
    if (!form) return;

    const formData = new FormData(form);
    const params = new URLSearchParams();
    const excluded = new Set([
      "category",
      "draft_category",
      "collection",
      "color",
      "size",
      "min_price",
      "max_price",
      "in_stock",
      "filter_preview",
    ]);

    for (const [key, value] of formData.entries()) {
      if (typeof value === "string" && value.trim() && !excluded.has(key)) {
        params.append(key, value);
      }
    }

    for (const value of formData.getAll("category")) {
      if (typeof value === "string" && value.trim()) {
        params.append("draft_category", value);
      }
    }

    params.set("filter_preview", "1");

    const destination = new URL(form.action, window.location.href);
    router.push(destination.pathname + "?" + params.toString());
  }

  return <div onChange={handleChange}>{children}</div>;
}
