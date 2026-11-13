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

const deploymentId = process.env.NEXT_PUBLIC_RELEASE_TAG;

const nextConfig: NextConfig = {
  // Bind Next.js client/server assets to one immutable release. Next.js forces a
  // hard navigation instead of mixing assets and RSC payloads across deployments.
  ...(deploymentId ? { deploymentId } : {}),
  // Small self-contained server bundle for the Docker image.
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;