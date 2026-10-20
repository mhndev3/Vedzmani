import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
];

/**
 * Image optimization is OPT-IN (build time). Default: every product image is
 * served as-is (`unoptimized`), exactly as before. Set BOTH
 *   IMAGE_OPTIMIZER=true
 *   MEDIA_CDN_BASE_URL=https://cdn.example.com[/prefix]   (same value as Django's)
 * to let Next's built-in optimizer (sharp, no paid service) resize and re-encode
 * (AVIF/WebP) images under that one base URL. Nothing else is ever optimized.
 * A misconfiguration fails the build loudly rather than silently doing nothing.
 * See docs/IMAGES.md.
 */
function optimizedMediaBase(): URL | null {
  if (process.env.IMAGE_OPTIMIZER !== "true") return null;
  const fail = (why: string): never => {
    throw new Error(`IMAGE_OPTIMIZER=true requires MEDIA_CDN_BASE_URL to be ${why}.`);
  };
  let url: URL;
  try {
    url = new URL((process.env.MEDIA_CDN_BASE_URL ?? "").trim());
  } catch {
    return fail("an absolute https:// URL");
  }
  if (url.protocol !== "https:") fail("an https:// URL");
  if (url.username || url.password) fail("free of credentials");
  if (url.search || url.hash) fail("free of a query string or fragment");
  return url;
}

const mediaBase = optimizedMediaBase();
const mediaPath = mediaBase ? mediaBase.pathname.replace(/\/+$/, "") : "";

const nextConfig: NextConfig = {
  // Small self-contained server bundle for the Docker image.
  output: "standalone",
  poweredByHeader: false,
  // Inlined into server and client code; read only by src/lib/images.ts.
  // Empty string = optimizer off.
  env: {
    NEXT_PUBLIC_MEDIA_OPTIMIZED_BASE: mediaBase ? `${mediaBase.origin}${mediaPath}` : "",
  },
  ...(mediaBase && {
    images: {
      // Exactly one origin + path prefix, no query strings: any other URL gets a 400.
      remotePatterns: [
        {
          protocol: "https",
          hostname: mediaBase.hostname,
          port: mediaBase.port,
          pathname: `${mediaPath}/**`,
          search: "",
        },
      ],
      formats: ["image/avif", "image/webp"],
      // Widest displayed image is ~1152 CSS px; drop the default 1920/2048/3840 steps
      // so nobody can make the server encode huge variants.
      deviceSizes: [640, 750, 828, 1080, 1200],
      // Storage keys are not content-hashed and the optimizer cannot invalidate its
      // cache, so keep this moderate (1 day) instead of "forever".
      minimumCacheTTL: 86400,
    },
  }),
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
