import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { legalDocumentBySlug, legalDocuments } from "@/lib/legal-content";

export const dynamicParams = false;

export function generateStaticParams() {
  return legalDocuments.map(({ slug }) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const document = legalDocumentBySlug.get(slug);
  return document
    ? { title: `${document.title} | RenderCart`, description: document.description }
    : { title: "Policy not found | RenderCart" };
}

export default async function LegalPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const document = legalDocumentBySlug.get(slug);
  if (!document) notFound();

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-6 py-10 sm:px-10">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5 dark:border-slate-800">
        <Link className="font-bold" href="/">RenderCart</Link>
        <nav aria-label="Policy pages" className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-600 dark:text-slate-300">
          {legalDocuments.map((item) => (
            <Link key={item.slug} href={`/legal/${item.slug}`} aria-current={item.slug === slug ? "page" : undefined}>
              {item.title}
            </Link>
          ))}
        </nav>
      </header>
      <article className="mx-auto max-w-3xl py-12">
        <p className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
          Draft template. Replace bracketed details and have this policy reviewed for your business and jurisdiction before launch.
        </p>
        <h1 className="mt-8 text-4xl font-semibold tracking-tight">{document.title}</h1>
        <p className="mt-4 text-sm text-slate-500">Last updated: [EFFECTIVE DATE]</p>
        <div className="mt-10 space-y-9">
          {document.sections.map((section) => (
            <section key={section.heading}>
              <h2 className="text-xl font-semibold">{section.heading}</h2>
              <div className="mt-3 space-y-3 text-base leading-7 text-slate-700 dark:text-slate-300">
                {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              </div>
            </section>
          ))}
        </div>
        <div className="mt-12 border-t border-slate-200 pt-6 text-sm text-slate-500 dark:border-slate-800">
          <Link href="/" className="font-medium text-violet-700 dark:text-violet-300">Return to RenderCart</Link>
        </div>
      </article>
    </main>
  );
}
