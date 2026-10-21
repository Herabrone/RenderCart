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
    ? {
        title: `${document.title} | RenderCart`,
        description: document.description,
      }
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
    <main className="legal-page">
      <div className="legal-layout">
        <aside className="category-nav">
          <p className="nav-label">The useful details</p>
          <nav aria-label="Policy pages">
            {legalDocuments.map((item) => (
              <Link
                key={item.slug}
                className={item.slug === slug ? "selected" : ""}
                href={`/legal/${item.slug}`}
                aria-current={item.slug === slug ? "page" : undefined}
              >
                {item.title}
              </Link>
            ))}
          </nav>
        </aside>
        <article className="legal-article">
          <p className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950   ">
            Draft template. Replace bracketed details and have this policy
            reviewed for your business and jurisdiction before launch.
          </p>
          <h1 className="mt-8 text-4xl font-semibold tracking-tight">
            {document.title}
          </h1>
          <p className="mt-4 text-sm text-muted">
            Last updated: [EFFECTIVE DATE]
          </p>
          <div className="mt-10 space-y-9">
            {document.sections.map((section) => (
              <section key={section.heading}>
                <h2 className="text-xl font-semibold">{section.heading}</h2>
                <div className="mt-3 space-y-3 text-base leading-7 text-ink ">
                  {section.paragraphs.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                </div>
              </section>
            ))}
          </div>
          <div className="mt-12 border-t border-line pt-6 text-sm text-muted ">
            <Link href="/" className="font-medium text-accent ">
              Return to RenderCart
            </Link>
          </div>
        </article>
      </div>
    </main>
  );
}
