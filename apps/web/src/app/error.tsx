"use client";
import Link from "next/link";
export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="error-panel">
      <span className="eyebrow">A small interruption</span>
      <h1>Something didn’t load.</h1>
      <p>Try again in a moment. You can also return to the tool library.</p>
      <div className="flex flex-wrap justify-center gap-3">
        <button className="button button-primary" onClick={() => reset()}>
          Try again
        </button>
        <Link href="/tools" className="button button-secondary">
          Browse tools
        </Link>
      </div>
    </main>
  );
}
