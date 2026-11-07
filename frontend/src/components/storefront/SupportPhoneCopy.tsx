"use client";

import { useEffect, useRef, useState } from "react";

type SupportPhoneCopyProps = {
  phone: string;
  displayPhone: string;
  label: string;
};

export function SupportPhoneCopy({ phone, displayPhone, label }: SupportPhoneCopyProps) {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  async function copyPhone() {
    try {
      await navigator.clipboard.writeText(phone);
      setCopied(true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), 1000);
    } catch {
      setCopied(false);
    }
  }

  const cardClassName =
    "w-full rounded-2xl border border-border bg-background/70 px-4 py-4 text-center transition-colors hover:bg-background";

  return (
    <>
      <a
        href={`tel:+98${phone.slice(1)}`}
        dir="rtl"
        className={`block sm:hidden ${cardClassName}`}
      >
        <span className="mb-1 block text-sm text-muted-foreground">{label}</span>
        <span className="font-semibold tabular-nums">{displayPhone}</span>
      </a>
      <button
        type="button"
        dir="rtl"
        onClick={copyPhone}
        aria-live="polite"
        className={`hidden sm:block ${cardClassName} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`}
      >
        <span className="mb-1 block text-sm text-muted-foreground">{label}</span>
        <span className="font-semibold tabular-nums">{copied ? "کپی شد" : displayPhone}</span>
      </button>
    </>
  );
}
