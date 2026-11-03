"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  label: string;
  className: string;
};

/** Shows an exact backend count for the current draft form without applying it. */
export function FilterApplyButton({ label, className }: Props) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    const form = buttonRef.current?.form;
    if (!form) return;

    let timer: ReturnType<typeof window.setTimeout> | undefined;
    let controller: AbortController | null = null;

    const refreshCount = () => {
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(async () => {
        controller?.abort();
        const requestController = new AbortController();
        controller = requestController;

        const params = new URLSearchParams();
        for (const [key, value] of new FormData(form).entries()) {
          if (
            typeof value === "string" &&
            value.trim() !== "" &&
            key !== "filters_open" &&
            key !== "filter_preview" &&
            key !== "draft_category"
          ) {
            params.append(key, value);
          }
        }
        params.set("page_size", "1");

        try {
          const response = await fetch("/api/catalog/variant-products/?" + params.toString(), {
            method: "GET",
            credentials: "same-origin",
            cache: "no-store",
            signal: requestController.signal,
            headers: { Accept: "application/json" },
          });
          if (!response.ok) throw new Error("filter_count_failed");
          const data = await response.json() as { count?: unknown };
          if (!requestController.signal.aborted && typeof data.count === "number") {
            setCount(data.count);
          }
        } catch {
          if (!requestController.signal.aborted) setCount(null);
        }
      }, 180);
    };

    form.addEventListener("change", refreshCount);
    form.addEventListener("input", refreshCount);
    refreshCount();

    return () => {
      if (timer) window.clearTimeout(timer);
      controller?.abort();
      form.removeEventListener("change", refreshCount);
      form.removeEventListener("input", refreshCount);
    };
  }, []);

  return (
    <button ref={buttonRef} type="submit" className={className}>
      {label}
      <span aria-live="polite">
        {count === null ? "" : " (" + count.toLocaleString("fa-IR") + ")"}
      </span>
    </button>
  );
}
