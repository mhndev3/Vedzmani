"use client";

import { useEffect, useState } from "react";

const ENAMAD_IMAGE_URL =
  "https://trustseal.enamad.ir/logo.aspx?id=8480737&Code=hThQ5QKm0EhDkGtXcKiXmh0BBbXTcwgm";
const ENAMAD_LINK_URL =
  "https://trustseal.enamad.ir/?id=8480737&Code=hThQ5QKm0EhDkGtXcKiXmh0BBbXTcwgm";
const MAX_RETRIES = 3;

export function EnamadSeal() {
  const [attempt, setAttempt] = useState(0);
  const [retryPending, setRetryPending] = useState(false);

  useEffect(() => {
    if (!retryPending || attempt >= MAX_RETRIES) return;

    const timer = window.setTimeout(() => {
      setRetryPending(false);
      setAttempt((current) => current + 1);
    }, 1000 * attempt);

    return () => window.clearTimeout(timer);
  }, [attempt, retryPending]);

  const imageUrl =
    attempt === 0 ? ENAMAD_IMAGE_URL : `${ENAMAD_IMAGE_URL}&retry=${attempt}`;

  return (
    <a
      referrerPolicy="origin"
      target="_blank"
      rel="noopener noreferrer"
      href={ENAMAD_LINK_URL}
      aria-label="مشاهده تأییدیه نماد اعتماد الکترونیکی"
    >
      <img
        src={imageUrl}
        alt="نماد اعتماد الکترونیکی"
        width={120}
        height={120}
        loading="eager"
        fetchPriority="high"
        decoding="async"
        referrerPolicy="origin"
        onError={() => {
          if (attempt < MAX_RETRIES) setRetryPending(true);
        }}
        style={{ width: 120, height: 120, objectFit: "contain", cursor: "pointer" }}
      />
    </a>
  );
}
