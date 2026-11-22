"use client";

const ENAMAD_CODE = "hThQ5QKm0EhDkGtXcKiXmh0BBbXTcwgm";
const ENAMAD_IMAGE_URL = `https://trustseal.enamad.ir/logo.aspx?id=8480737&Code=${ENAMAD_CODE}`;
const ENAMAD_LINK_URL = `https://trustseal.enamad.ir/?id=8480737&Code=${ENAMAD_CODE}`;

export function EnamadSeal() {
  return (
    <a
      referrerPolicy="origin"
      target="_blank"
      href={ENAMAD_LINK_URL}
    >
      <img
        referrerPolicy="origin"
        src={ENAMAD_IMAGE_URL}
        alt=""
        style={{ cursor: "pointer" }}
        code={ENAMAD_CODE}
      />
    </a>
  );
}
