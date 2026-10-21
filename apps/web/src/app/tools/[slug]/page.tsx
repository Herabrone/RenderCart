import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ArrowUpRight,
  ChevronRight,
  LayoutGrid,
  ShieldCheck,
} from "lucide-react";
import { categories } from "@/components/tool-catalog";
import { JobRunner } from "@/lib/job-runner";
import { ClientToolRunner } from "@/lib/client-tool-runner";
import { clientTools } from "@/lib/client-tools";
import { PdfChatPanel } from "@/lib/pdf-chat";
import { DynamicQrManager } from "@/lib/dynamic-qr-manager";
import { WebsiteAuditHistory } from "@/lib/website-audit-history";

type Tool = {
  slug: string;
  name: string;
  category: string;
  summary: string;
  runtime?: string;
  min_level?: string;
  batchable?: boolean;
  batch_max_files?: number | null;
  job_tier?: "S" | "M" | "L" | null;
  single_job_price_cents?: number | null;
  prices?: Record<string, number>;
  credit_cost?: number | null;
  credit_cost_per_page?: number;
  credit_cost_per_10_pages?: number;
  credit_cost_per_100_mb?: number;
  credit_cost_per_minute?: number;
  credit_cost_per_10_minutes?: number;
  credit_cost_per_10000_words?: number;
  credit_cost_per_1000_words?: number;
  credit_cost_per_1000_chars?: number;
  limits?: Record<
    string,
    {
      max_pages?: number;
      max_minutes_per_month?: number;
      max_characters_per_job?: number;
      max_words_per_job?: number;
      word_count_per_day?: number;
    }
  >;
  seo: { title: string; description: string };
  inputs: { accept: string[]; min_files: number } | null;
  options_schema: {
    properties?: Record<
      string,
      {
        default?: unknown;
        description?: string;
        enum?: string[];
        format?: string;
        maximum?: number;
        minimum?: number;
        title?: string;
        type?: string;
        maxLength?: number;
      }
    >;
  } | null;
};

async function getTool(slug: string): Promise<Tool | null> {
  try {
    const response = await fetch(
      `${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/tools/${slug}`,
      { next: { revalidate: 300 } },
    );
    if (response.ok) return (await response.json()) as Tool;
  } catch {
    /* Use browser-only manifests while the API is unavailable. */
  }
  return clientTools.find((tool) => tool.slug === slug) ?? null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const tool = await getTool(slug);
  return tool
    ? { title: tool.seo.title, description: tool.seo.description }
    : { title: "Tool not found | RenderCart" };
}

export default async function ToolPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const tool = await getTool(slug);
  if (!tool) notFound();
  const category = categories.find((c) => c.slug === tool.category);
  const Icon = category?.icon ?? LayoutGrid;
  const local = tool.runtime === "client" && tool.slug !== "qr-dynamic";
  const related = clientTools
    .filter((t) => t.category === tool.category && t.slug !== tool.slug)
    .slice(0, 3);
  const singlePrice =
    tool.prices?.[`job_${(tool.job_tier ?? "S").toLowerCase()}`] ??
    tool.single_job_price_cents;
  const hasUsage =
    typeof singlePrice === "number" ||
    [
      tool.credit_cost,
      tool.credit_cost_per_page,
      tool.credit_cost_per_10_pages,
      tool.credit_cost_per_100_mb,
      tool.credit_cost_per_minute,
      tool.credit_cost_per_10_minutes,
      tool.credit_cost_per_10000_words,
      tool.credit_cost_per_1000_words,
      tool.credit_cost_per_1000_chars,
    ].some(Boolean) ||
    Object.values(tool.limits ?? {}).some((limit) =>
      Object.values(limit).some(Boolean),
    );
  const creditAudience =
    tool.min_level === "pro" ? "Pro usage" : "Pro and day-pass usage";
  return (
    <main className="tool-page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/tools">All tools</Link>
        <ChevronRight size={12} />
        <Link href={`/categories/${tool.category}`}>
          {category?.name ?? tool.category}
        </Link>
      </nav>
      <header className="tool-heading">
        <span className={`tool-icon tone-${category?.tone ?? "sage"}`}>
          <Icon size={25} strokeWidth={1.6} />
        </span>
        <div>
          <span className="tool-heading-label">
            {local ? "IN YOUR BROWSER" : "YOUR FILE WORKSPACE"}
          </span>
          <h1>{tool.name}</h1>
          <p>{tool.summary}</p>
        </div>
      </header>
      <div className="tool-workspace">
        <section
          className="tool-work-area"
          aria-label={`${tool.name} workspace`}
        >
          <div className="workspace-bar">
            <strong>{local ? "Make it your own" : "Set up your job"}</strong>
            <span>{local ? "No upload needed" : "Ready when you are"}</span>
          </div>
          {tool.slug === "qr-dynamic" ? (
            <DynamicQrManager />
          ) : tool.runtime === "client" ? (
            <ClientToolRunner slug={tool.slug} />
          ) : (
            <JobRunner tool={tool} />
          )}
          {tool.slug === "chat-with-pdf" ? <PdfChatPanel /> : null}
          {tool.slug === "website-audit" ? <WebsiteAuditHistory /> : null}
        </section>
        <aside className="tool-side">
          <h2>A simple way through.</h2>
          <p>
            {local
              ? "Add your content, choose your options, and copy or download the result."
              : "Choose your files, set the options, and run your tool. Your result will appear on its own job page."}
          </p>
          <hr />
          <ShieldCheck size={19} />
          <p>
            {local
              ? "Your content stays on this device."
              : "Uploaded job files expire automatically. Download your results before their expiry time."}
          </p>
          {hasUsage && (
            <details open>
              <summary>Usage & limits</summary>
              <div className="tool-costs">
                {typeof singlePrice === "number" && (
                  <p>
                    Single job:{" "}
                    <strong>${(singlePrice / 100).toFixed(2)}</strong>, if you
                    need to go beyond the free allowance.
                  </p>
                )}
                {tool.credit_cost ? (
                  <p className="mt-3 text-sm text-muted">
                    {creditAudience}: {tool.credit_cost}{" "}
                    {tool.credit_cost === 1 ? "credit" : "credits"} per job.
                  </p>
                ) : null}
                {tool.credit_cost_per_page ? (
                  <p className="mt-3 text-sm text-muted">
                    {creditAudience}: {tool.credit_cost_per_page} credits per
                    page.
                  </p>
                ) : null}
                {tool.credit_cost_per_10_pages ? (
                  <p className="mt-3 text-sm text-muted">
                    {creditAudience}: {tool.credit_cost_per_10_pages}{" "}
                    {tool.credit_cost_per_10_pages === 1 ? "credit" : "credits"}{" "}
                    per 10 pages.
                  </p>
                ) : null}
                {tool.credit_cost_per_100_mb ? (
                  <p className="mt-3 text-sm text-muted">
                    {creditAudience}: {tool.credit_cost_per_100_mb}{" "}
                    {tool.credit_cost_per_100_mb === 1 ? "credit" : "credits"}{" "}
                    per 100 MB.
                  </p>
                ) : null}
                {tool.credit_cost_per_minute ? (
                  <p className="mt-3 text-sm text-muted">
                    {creditAudience}: {tool.credit_cost_per_minute}{" "}
                    {tool.credit_cost_per_minute === 1 ? "credit" : "credits"}{" "}
                    per started minute.
                  </p>
                ) : null}
                {tool.credit_cost_per_10_minutes ? (
                  <p className="mt-3 text-sm text-muted">
                    {creditAudience}: {tool.credit_cost_per_10_minutes}{" "}
                    {tool.credit_cost_per_10_minutes === 1
                      ? "credit"
                      : "credits"}{" "}
                    per started 10 minutes.
                  </p>
                ) : null}
                {tool.credit_cost_per_10000_words ? (
                  <p className="mt-3 text-sm text-muted">
                    {creditAudience}: {tool.credit_cost_per_10000_words}{" "}
                    {tool.credit_cost_per_10000_words === 1
                      ? "credit"
                      : "credits"}{" "}
                    per started 10,000 words, plus the per-job cost.
                  </p>
                ) : null}
                {tool.credit_cost_per_1000_words ? (
                  <p className="mt-3 text-sm text-muted">
                    {creditAudience}: {tool.credit_cost_per_1000_words}{" "}
                    {tool.credit_cost_per_1000_words === 1
                      ? "credit"
                      : "credits"}{" "}
                    per started 1,000 words.
                  </p>
                ) : null}
                {tool.credit_cost_per_1000_chars ? (
                  <p className="mt-3 text-sm text-muted">
                    {creditAudience}: {tool.credit_cost_per_1000_chars}{" "}
                    {tool.credit_cost_per_1000_chars === 1
                      ? "credit"
                      : "credits"}{" "}
                    per 1,000 characters.
                  </p>
                ) : null}
                {tool.limits?.guest?.max_minutes_per_month ||
                tool.limits?.free?.max_minutes_per_month ? (
                  <p className="mt-2 text-sm text-muted">
                    Free monthly transcription:{" "}
                    {tool.limits.guest?.max_minutes_per_month ?? 0} minutes for
                    guests, {tool.limits.free?.max_minutes_per_month ?? 0}{" "}
                    minutes for free accounts.
                  </p>
                ) : null}
                {tool.limits?.guest?.max_characters_per_job ||
                tool.limits?.free?.max_characters_per_job ? (
                  <p className="mt-2 text-sm text-muted">
                    Text limits:{" "}
                    {tool.limits.guest?.max_characters_per_job ?? 0} characters
                    for guests and{" "}
                    {tool.limits.free?.max_characters_per_job ?? 0} for free
                    accounts.
                  </p>
                ) : null}
                {tool.limits?.guest?.max_words_per_job ||
                tool.limits?.free?.max_words_per_job ? (
                  <p className="mt-2 text-sm text-muted">
                    Free input limit: up to{" "}
                    {tool.limits.guest?.max_words_per_job ??
                      tool.limits.free?.max_words_per_job}{" "}
                    words per job.
                  </p>
                ) : null}
                {tool.limits?.guest?.max_pages ||
                tool.limits?.free?.max_pages ? (
                  <p className="mt-2 text-sm text-muted">
                    Free document limit:{" "}
                    {tool.limits.guest?.max_pages ??
                      tool.limits.free?.max_pages}{" "}
                    page per job. Pro and day-pass users can translate full
                    documents.
                  </p>
                ) : null}
                {tool.limits?.guest?.word_count_per_day ||
                tool.limits?.free?.word_count_per_day ? (
                  <p className="mt-2 text-sm text-muted">
                    Free daily limit:{" "}
                    {tool.limits.guest?.word_count_per_day ??
                      tool.limits.free?.word_count_per_day}{" "}
                    words.
                  </p>
                ) : null}
              </div>
            </details>
          )}
          {related.length > 0 && (
            <>
              <hr />
              <h2>While you’re here</h2>
              {related.map((t) => (
                <Link key={t.slug} href={`/tools/${t.slug}`}>
                  {t.name}
                  <ArrowUpRight size={14} />
                </Link>
              ))}
            </>
          )}
        </aside>
      </div>
    </main>
  );
}
