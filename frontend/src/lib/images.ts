/**
 * Per-image delivery choice for next/image (see docs/IMAGES.md).
 *
 * `NEXT_PUBLIC_MEDIA_OPTIMIZED_BASE` is set by next.config.ts at build time and is
 * empty unless IMAGE_OPTIMIZER=true with a valid https MEDIA_CDN_BASE_URL. Only URLs
 * under exactly that base use Next's optimizer; everything else (origin-relative
 * `/<key>` paths, any other host, no image) stays `unoptimized`, i.e. unchanged.
 * Safe in Server and Client Components: the value is inlined at build time.
 */
const OPTIMIZED_BASE = process.env.NEXT_PUBLIC_MEDIA_OPTIMIZED_BASE ?? "";

export function imageDelivery(url: string): { unoptimized: boolean } {
  return { unoptimized: !OPTIMIZED_BASE || !url.startsWith(`${OPTIMIZED_BASE}/`) };
}

/**
 * `sizes` hints that match the real layout (max-w-6xl = 1152px container, 1rem
 * padding). They only take effect when the optimizer generates a `srcset`.
 */
export const IMAGE_SIZES = {
  /** Catalog grid: 2 / 3 / 4 columns; 4th column width capped at the 1152px container. */
  catalogCard: "(min-width:1152px) 268px, (min-width:1024px) 25vw, (min-width:640px) 33vw, 50vw",
  /** Product page, first (full-width) gallery image. Column is ~544px at >=1152px. */
  galleryMain: "(min-width:1152px) 544px, (min-width:768px) 50vw, 100vw",
  /** Product page, remaining gallery images (two per row). */
  galleryThumb: "(min-width:1152px) 266px, (min-width:768px) 25vw, 50vw",
  /** Cart line thumbnail (w-20 / sm:w-24 = 80-96px). */
  cartThumb: "96px",
} as const;
