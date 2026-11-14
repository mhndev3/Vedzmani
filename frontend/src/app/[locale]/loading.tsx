/** Shared App Router fallback while a storefront route is being rendered. */
export default function StorefrontLoading() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8" aria-busy="true">
      <div className="h-8 w-48 animate-pulse rounded-lg bg-muted motion-reduce:animate-none" />
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, index) => (
          <div key={index}>
            <div className="aspect-[3/4] animate-pulse rounded-xl bg-muted motion-reduce:animate-none" />
            <div className="mt-3 h-4 w-3/4 animate-pulse rounded bg-muted motion-reduce:animate-none" />
            <div className="mt-2 h-4 w-1/3 animate-pulse rounded bg-muted motion-reduce:animate-none" />
          </div>
        ))}
      </div>
    </div>
  );
}
