/** Framework-native category loading UI; keeps navigation responsive while products load. */
export default function CategoryLoading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8" aria-busy="true" aria-label="در حال بارگذاری دسته‌بندی">
      <div className="h-8 w-40 animate-pulse rounded-lg bg-muted motion-reduce:animate-none" />
      <div className="mt-6 h-12 rounded-2xl bg-muted animate-pulse motion-reduce:animate-none" />
      <ul className="mt-6 grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, index) => (
          <li key={index}>
            <div className="aspect-[3/4] animate-pulse rounded-lg bg-muted motion-reduce:animate-none" />
            <div className="mt-3 h-4 w-3/4 animate-pulse rounded bg-muted motion-reduce:animate-none" />
            <div className="mt-2 h-4 w-1/3 animate-pulse rounded bg-muted motion-reduce:animate-none" />
          </li>
        ))}
      </ul>
    </div>
  );
}
