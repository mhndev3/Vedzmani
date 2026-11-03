"use client";

import type { ChangeEvent, FormEvent, ReactNode } from "react";

/**
 * A category selection is a facet-preview step, not an applied product filter.
 * Submit draft_category so the server can refresh dependent options while the
 * product result query remains unchanged. The mobile drawer stays open for preview.
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

    form.querySelectorAll<HTMLInputElement>('input[name="category"]').forEach((field) => {
      field.name = "draft_category";
    });

    let preview = form.querySelector<HTMLInputElement>('input[name="filter_preview"]');
    if (!preview) {
      preview = document.createElement("input");
      preview.type = "hidden";
      preview.name = "filter_preview";
      preview.value = "1";
      form.appendChild(preview);
    }

    form.requestSubmit();
  }

  function handleSubmit(event: FormEvent<HTMLDivElement>) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    // requestSubmit() without a submitter is the category-preview navigation.
    // A real submit button means the customer is applying the finished filters.
    const submitter = (event.nativeEvent as SubmitEvent).submitter;
    if (submitter) {
      form.querySelector<HTMLInputElement>('input[name="filter_preview"]')?.remove();
      form.querySelectorAll<HTMLInputElement>('input[name="draft_category"]').forEach((field) => {
        field.name = "category";
      });
      form.querySelector<HTMLInputElement>('input[name="filters_open"]')?.remove();
    }
  }

  return <div onChange={handleChange} onSubmit={handleSubmit}>{children}</div>;
}
