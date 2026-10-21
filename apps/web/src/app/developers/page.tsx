import Link from "next/link";

export const metadata = {
  title: "Developer API | RenderCart",
  description:
    "Run RenderCart tools from your application with the public API.",
};

export default function DevelopersPage() {
  return (
    <main className="mx-auto min-h-screen max-w-4xl px-6 py-12">
      <header className="flex items-center justify-between">
        <Link href="/" className="text-xl font-bold">
          RenderCart<span className="text-violet-600">.</span>
        </Link>
        <Link href="/account" className="text-sm font-semibold text-violet-700">
          Manage API keys
        </Link>
      </header>
      <article className="mt-14 rounded-3xl border border-slate-200 bg-white p-8 dark:border-slate-700 dark:bg-slate-900">
        <h1 className="text-3xl font-semibold">Developer API</h1>
        <p className="mt-3 text-slate-600 dark:text-slate-300">
          Use a Pro account API key to discover public tools, upload inputs, and
          run jobs. Requests are limited to 120 per minute per key. Jobs use the
          same validation, access rules, and credit billing as website jobs.
        </p>
        <a
          className="mt-5 inline-flex rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold dark:border-slate-600"
          href="/v1/openapi.json"
        >
          OpenAPI schema
        </a>
        <h2 className="mt-10 text-xl font-semibold">Authentication</h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
          Send your key in an Authorization header. Create and revoke keys from
          your account page. A new key is shown once.
        </p>
        <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950 p-4 text-sm text-slate-100">
          <code>{`Authorization: Bearer rc_live_…`}</code>
        </pre>
        <h2 className="mt-10 text-xl font-semibold">Run a file tool</h2>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-600 dark:text-slate-300">
          <li>
            Call <code>POST /v1/uploads/presign</code> with the tool slug,
            filename, MIME type, and byte size.
          </li>
          <li>
            PUT the file to the returned upload URL using the returned headers.
          </li>
          <li>
            Call <code>POST /v1/tools/merge-pdf/jobs</code> with the upload ID
            and tool options.
          </li>
          <li>
            Poll the returned status URL until the job succeeds, then use its
            download URL.
          </li>
        </ol>
        <pre className="mt-4 overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-100">
          <code>{`curl -X POST https://rendercart.example/v1/tools/merge-pdf/jobs \\
  -H "Authorization: Bearer rc_live_…" \\
  -H "Content-Type: application/json" \\
  -d '{"upload_ids":["UPLOAD_UUID_1","UPLOAD_UUID_2"],"options":{}}'`}</code>
        </pre>
        <p className="mt-5 text-xs text-slate-500">
          File URLs expire. Do not expose API keys in browser code or public
          repositories. Disabled and restricted tools are not available through
          the public API.
        </p>
      </article>
    </main>
  );
}
