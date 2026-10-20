# Product image delivery

Last updated: 2026-10-21 (Agent 2, session 1). Labels: **verified** = executed and the result inspected;
**inferred** = derived from reading code/docs, not executed; **not verified** = no evidence either way.

## 1. What is and is not configured

- Product images are stored as WebP **metadata only** (`backend/apps/catalog/storage.py`); there is no upload or
  conversion pipeline, no storage vendor and no CDN configured by this repository.
- **Default behaviour is unchanged**: every `next/image` is `unoptimized`, so each browser downloads the single stored
  file at its stored size. `sizes` has no effect in that mode (no `srcset` is produced).
- This change adds an **opt-in** way to resize/re-encode images with Next's built-in optimizer (free, self-hosted,
  uses the `sharp` that ships with Next). It does not select, configure or require a CDN or storage vendor.

## 2. Known problem: origin-relative image URLs (not fixed here)

`public_image_url()` returns `<MEDIA_CDN_BASE_URL>/<key>`, or **`/<key>` when `MEDIA_CDN_BASE_URL` is empty or unset**.
A `/<key>` URL is requested from the site's own origin. In the compose topology nginx sends only `/api/` and `/admin/`
to Django and everything else (`location /`) to Next.js, which has no such file (`frontend/public` is empty), so
**every product image 404s whenever `MEDIA_CDN_BASE_URL` is unset** (inferred from `nginx/default.conf` and `storage.py`).
Fixing it is a hosting decision for the owner: point `MEDIA_CDN_BASE_URL` at the real bucket/CDN, or add a media route
in nginx. Neither was done. Origin-relative URLs are never optimized (see 3), so they behave exactly as before.

## 3. Optional image optimizer

Build-time variables (non-secret; both empty/unset = off):

| Variable | Value |
| --- | --- |
| `IMAGE_OPTIMIZER` | `true` to enable |
| `MEDIA_CDN_BASE_URL` | `https://host[:port][/prefix]`, same value as Django's. No credentials, query or fragment. |

- Invalid values **fail the build** with a message (verified for: unset, `http://`, credentials, query, relative, garbage).
- `next.config.ts` then allows exactly one `remotePatterns` entry (https, that host and port, `/prefix/**`, no query) and
  `src/lib/images.ts` optimizes only URLs that start with that base; other URLs stay `unoptimized`.
- Also set when enabled: formats `avif`, `webp`; `deviceSizes` 640, 750, 828, 1080, 1200 (the 1920/2048/3840 defaults are
  removed); `minimumCacheTTL` 86400 (1 day); quality stays at the default 75.
- Docker: the `frontend/Dockerfile` build stage accepts `--build-arg IMAGE_OPTIMIZER=true --build-arg MEDIA_CDN_BASE_URL=...`.
  `docker-compose.yml` was **not** changed and passes neither argument; add both under `frontend.build.args` to enable it there.
- The optimizer fetches the originals from the CDN server-side, so the frontend container needs outbound HTTPS to that host.
- `next start` re-evaluates `next.config.ts` at start-up (verified): with it, set both variables at runtime too, otherwise the
  HTML points at `/_next/image` while the server rejects every URL with 400. `node server.js` from the standalone output (what the
  Dockerfile runs) embeds the config at build time.

## 4. Requirements for a proxy / CDN in front of the site

- **Forward the `Accept` header for `/_next/image` and include it in the cache key** (Next answers with `Vary: Accept`; verified).
  Otherwise an AVIF/WebP response can be cached and served to a client that did not ask for it.
- Do not cache `/_next/image` responses longer than you can tolerate stale images (section 5).

## 5. Caching limits

- The repository sets **no** cache headers for product images; they come from the storage/CDN. No change was made.
- Observed optimizer headers: `Cache-Control: public, max-age=86400, must-revalidate`, `Vary: Accept`.
- The optimizer cannot invalidate its cache. Storage keys are **not content-hashed**, so replacing an object keeps its key.
  Therefore **`immutable` / very long TTLs are unsafe** on the bucket, CDN or `/_next/image` until keys carry a content hash or
  version. Until then keep TTLs moderate and purge on replacement.

## 6. `sizes` hints

`IMAGE_SIZES` in `src/lib/images.ts` encodes the real layout (container `max-w-6xl` = 1152px, 16px padding; catalog cards
about 268px wide at 1152px+, product-page main image about 544px, thumbnails about 266px, cart thumbnail 96px). They only
matter when the optimizer is on. Update them if those layouts change. Underestimating makes images blurry; overestimating
wastes bytes.

## 7. Verification record (2026-10-21)

Executed: lint, typecheck and production build (default mode and several optimizer configurations); a scratch copy
of the app with a local fixture "CDN" and mock catalog API, using `next start`.

- **Synthetic fixtures only**: generated 1200x1600 noise WebP files (about 230 KB), not product assets. The byte counts show
  the mechanism, not savings on real product photos.

| Variant (one fixture, original 229,470 B) | AVIF | WebP | JPEG fallback |
| --- | --- | --- | --- |
| w=640 | 33,006 B | 43,588 B | 49,722 B |
| w=828 | 56,107 B | 71,860 B | 87,405 B |
| w=1200 | 122,341 B | 174,086 B | 185,604 B |

- verified: generated `srcset`/`sizes`, eager vs lazy and width/height preserved, requested dimensions returned, and HTTP 400 for a
  foreign host, another path prefix, a query string, the wrong protocol, unconfigured widths (1920, 3840), a disallowed quality
  and a local path. To test over `http` on loopback the scratch copy changed three lines of `next.config.ts` (protocol,
  `http:` check, `dangerouslyAllowLocalIP`); that is not in the repository.
- **Silent fallback**: if `sharp` cannot load, Next serves the **original** image with HTTP 200 and no visible error. This
  happened in the Windows standalone bundle (verified): Next's tracer includes `@img/sharp-libvips*`, but on Windows the DLLs live
  in `@img/sharp-win32-x64/lib`, so they were missing. On Linux libvips is a separate package matching that pattern (inferred).
  **After deploying, check once**: request `/_next/image?url=<encoded image URL>&w=640&q=75` with `Accept: image/avif` and
  confirm `Content-Type: image/avif` and fewer bytes than the original.
- **not verified**: the Linux Docker image (the Docker engine was not running), real product images, LCP/CLS in a browser,
  any CDN/proxy behaviour, `docker-compose.yml` with the build args.

## 8. Open items

Choice of storage/CDN vendor; fixing the origin-relative URL problem (section 2); passing the build args in compose;
cache headers on the storage side; whether four `fetchPriority="high"` images on the catalog list is right on narrow screens
(unchanged, not measured); `preconnect` to a CDN origin in unoptimized mode (not measured).
