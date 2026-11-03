"use client";

import { useRouter } from "next/navigation";
import type { ChangeEvent, FormEvent, ReactNode } from "react";

/**
 * Category selection previews dependent facets without applying the filter.
 * Both preview and apply navigations are built from FormData; React-owned
 * inputs are never renamed, removed, or appended imperatively.
 */
export function CategoryFilterAutoSubmit({ children }: { children: ReactNode }) {
  const router = useRouter();

  function destinationFor(form: HTMLFormElement, params: URLSearchParams) {
    const destination = new URL(form.action, window.location.href);
    return destination.pathname + (params.size ? "?" + params.toString() : "");
  }

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
    router.push(destinationFor(form, params));
  }

  function handleSubmit(event: FormEvent<HTMLDivElement>) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const submitter = (event.nativeEvent as SubmitEvent).submitter;
    if (!submitter) return;

    event.preventDefault();
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(form).entries()) {
      if (
        typeof value === "string" &&
        value.trim() &&
        key !== "filters_open" &&
        key !== "filter_preview" &&
        key !== "draft_category" &&
        !key.startsWith("applied_")
      ) {
        params.append(key, value);
      }
    }
    router.push(destinationFor(form, params));
  }

  return <div onChange={handleChange} onSubmitCapture={handleSubmit}>{children}</div>;
}
