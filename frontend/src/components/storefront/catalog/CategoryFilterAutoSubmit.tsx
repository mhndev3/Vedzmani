"use client";

import type { ChangeEvent, ReactNode } from "react";

/**
 * Selecting a top-level category immediately refreshes the server-rendered
 * facet vocabulary. Dependent selections are cleared so a colour/size from a
 * previous category cannot silently make the new category look empty.
 */
export function CategoryFilterAutoSubmit({ children }: { children: ReactNode }) {
  function handleChange(event: ChangeEvent<HTMLDivElement>) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || target.name !== "category" || target.type !== "checkbox") return;

    const form = target.form;
    if (!form) return;

    const dependentFields = form.querySelectorAll<HTMLInputElement>(
      'input[name="collection"], input[name="color"], input[name="size"], input[name="min_price"], input[name="max_price"], input[name="in_stock"]',
    );
    dependentFields.forEach((field) => {
      if (field.type === "checkbox") field.checked = false;
      else field.value = "";
    });

    form.requestSubmit();
  }

  return <div onChange={handleChange}>{children}</div>;
}
