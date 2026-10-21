import Link from "next/link";
import { ArrowLeft } from "lucide-react";
export default function NotFound() {
  return (
    <main className="error-panel">
      <span className="eyebrow">404 · Nothing here</span>
      <h1>Let’s find a better place to start.</h1>
      <p>
        This page isn’t available. The tool library is a good place to pick
        things up.
      </p>
      <Link className="button button-primary" href="/tools">
        <ArrowLeft size={16} />
        Back to the tools
      </Link>
    </main>
  );
}
