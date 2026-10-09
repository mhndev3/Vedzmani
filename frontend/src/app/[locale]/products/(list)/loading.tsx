/** Framework-native loading UI (no client JS): a reserved-size skeleton so the page does not shift. */
export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8" aria-busy="true">
      <div className="h-8 w-40 rounded-lg bg-muted" />
      <div className="mt-4 h-10 max-w-xl rounded-lg bg-muted" />
      <ul className="mt-10 grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <li key={i} className="animate-pulse motion-reduce:animate-none">
            <div className="aspect-[3/4] rounded-lg bg-muted" />
            <div className="mt-3 h-4 w-3/4 rounded bg-muted" />
            <div className="mt-2 h-4 w-1/3 rounded bg-muted" />
          </li>
        ))}
      </ul>
    </div>
  );
}
