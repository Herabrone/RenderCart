export default function Loading() {
  return (
    <div className="page-width py-16" role="status" aria-label="Loading page">
      <div className="h-3 w-28 rounded bg-subtle" />
      <div className="mt-5 h-10 w-2/3 max-w-lg rounded bg-subtle" />
      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-52 rounded-2xl border border-line bg-surface"
          />
        ))}
      </div>
      <span className="sr-only">Loading your workspace…</span>
    </div>
  );
}
