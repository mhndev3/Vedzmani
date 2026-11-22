"use client";

import type { ImgHTMLAttributes } from "react";

const ENAMAD_CODE = "hThQ5QKm0EhDkGtXcKiXmh0BBbXTcwgm";
const ENAMAD_IMAGE_URL = `https://trustseal.enamad.ir/logo.aspx?id=8480737&Code=${ENAMAD_CODE}`;
const ENAMAD_LINK_URL = `https://trustseal.enamad.ir/?id=8480737&Code=${ENAMAD_CODE}`;

const ENAMAD_IMAGE_ATTRIBUTES = {
  referrerPolicy: "origin",
  src: ENAMAD_IMAGE_URL,
  alt: "",
  style: { cursor: "pointer" },
  code: ENAMAD_CODE,
} as ImgHTMLAttributes<HTMLImageElement> & { code: string };

export function EnamadSeal() {
  return (
    <a
      referrerPolicy="origin"
      target="_blank"
      href={ENAMAD_LINK_URL}
    >
      <img {...ENAMAD_IMAGE_ATTRIBUTES} />
    </a>
  );
}
