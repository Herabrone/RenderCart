import Link from "next/link";
export function Brand() {
  return (
    <Link href="/" className="brand" aria-label="RenderCart home">
      <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <rect width="32" height="32" rx="9" fill="currentColor" />
        <path
          d="M9 11h8a5 5 0 0 1 0 10h-2m4-6 4 4-4 4M9 16h5M9 21h2"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span>RenderCart</span>
    </Link>
  );
}
