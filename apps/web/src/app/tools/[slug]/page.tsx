import { notFound } from "next/navigation";
import Link from "next/link";
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
  const creditAudience =
    tool.min_level === "pro" ? "Pro usage" : "Pro and day-pass usage";
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-10">
      <Link
        href="/tools"
        className="text-sm font-medium text-violet-700 dark:text-violet-300"
      >
        ← All tools
      </Link>
      <p className="mt-12 text-sm font-semibold uppercase tracking-widest text-violet-600">
        {tool.category}
      </p>
      <h1 className="mt-3 text-4xl font-semibold">{tool.name}</h1>
      <p className="mt-4 text-lg leading-8 text-slate-600 dark:text-slate-300">
        {tool.summary}
      </p>
      {tool.credit_cost ? (
        <p className="mt-3 text-sm text-slate-500">
          {creditAudience}: {tool.credit_cost}{" "}
          {tool.credit_cost === 1 ? "credit" : "credits"} per job.
        </p>
      ) : null}
      {tool.credit_cost_per_page ? (
        <p className="mt-3 text-sm text-slate-500">
          {creditAudience}: {tool.credit_cost_per_page} credits per page.
        </p>
      ) : null}
      {tool.credit_cost_per_10_pages ? (
        <p className="mt-3 text-sm text-slate-500">
          {creditAudience}: {tool.credit_cost_per_10_pages}{" "}
          {tool.credit_cost_per_10_pages === 1 ? "credit" : "credits"} per 10
          pages.
        </p>
      ) : null}
      {tool.credit_cost_per_100_mb ? (
        <p className="mt-3 text-sm text-slate-500">
          {creditAudience}: {tool.credit_cost_per_100_mb}{" "}
          {tool.credit_cost_per_100_mb === 1 ? "credit" : "credits"} per 100 MB.
        </p>
      ) : null}
      {tool.credit_cost_per_minute ? (
        <p className="mt-3 text-sm text-slate-500">
          {creditAudience}: {tool.credit_cost_per_minute}{" "}
          {tool.credit_cost_per_minute === 1 ? "credit" : "credits"} per started
          minute.
        </p>
      ) : null}
      {tool.credit_cost_per_10_minutes ? (
        <p className="mt-3 text-sm text-slate-500">
          {creditAudience}: {tool.credit_cost_per_10_minutes}{" "}
          {tool.credit_cost_per_10_minutes === 1 ? "credit" : "credits"} per
          started 10 minutes.
        </p>
      ) : null}
      {tool.credit_cost_per_10000_words ? (
        <p className="mt-3 text-sm text-slate-500">
          {creditAudience}: {tool.credit_cost_per_10000_words}{" "}
          {tool.credit_cost_per_10000_words === 1 ? "credit" : "credits"} per
          started 10,000 words, plus the per-job cost.
        </p>
      ) : null}
      {tool.credit_cost_per_1000_words ? (
        <p className="mt-3 text-sm text-slate-500">
          {creditAudience}: {tool.credit_cost_per_1000_words}{" "}
          {tool.credit_cost_per_1000_words === 1 ? "credit" : "credits"} per
          started 1,000 words.
        </p>
      ) : null}
      {tool.credit_cost_per_1000_chars ? (
        <p className="mt-3 text-sm text-slate-500">
          {creditAudience}: {tool.credit_cost_per_1000_chars}{" "}
          {tool.credit_cost_per_1000_chars === 1 ? "credit" : "credits"} per
          1,000 characters.
        </p>
      ) : null}
      {tool.limits?.guest?.max_minutes_per_month ||
      tool.limits?.free?.max_minutes_per_month ? (
        <p className="mt-2 text-sm text-slate-500">
          Free monthly transcription:{" "}
          {tool.limits.guest?.max_minutes_per_month ?? 0} minutes for guests,{" "}
          {tool.limits.free?.max_minutes_per_month ?? 0} minutes for free
          accounts.
        </p>
      ) : null}
      {tool.limits?.guest?.max_characters_per_job ||
      tool.limits?.free?.max_characters_per_job ? (
        <p className="mt-2 text-sm text-slate-500">
          Text limits: {tool.limits.guest?.max_characters_per_job ?? 0}{" "}
          characters for guests and{" "}
          {tool.limits.free?.max_characters_per_job ?? 0} for free accounts.
        </p>
      ) : null}
      {tool.limits?.guest?.max_words_per_job ||
      tool.limits?.free?.max_words_per_job ? (
        <p className="mt-2 text-sm text-slate-500">
          Free input limit: up to{" "}
          {tool.limits.guest?.max_words_per_job ??
            tool.limits.free?.max_words_per_job}{" "}
          words per job.
        </p>
      ) : null}
      {tool.limits?.guest?.max_pages || tool.limits?.free?.max_pages ? (
        <p className="mt-2 text-sm text-slate-500">
          Free document limit:{" "}
          {tool.limits.guest?.max_pages ?? tool.limits.free?.max_pages} page per
          job. Pro and day-pass users can translate full documents.
        </p>
      ) : null}
      {tool.limits?.guest?.word_count_per_day ||
      tool.limits?.free?.word_count_per_day ? (
        <p className="mt-2 text-sm text-slate-500">
          Free daily limit:{" "}
          {tool.limits.guest?.word_count_per_day ??
            tool.limits.free?.word_count_per_day}{" "}
          words.
        </p>
      ) : null}
      {tool.slug === "qr-dynamic" ? (
        <DynamicQrManager />
      ) : tool.runtime === "client" ? (
        <ClientToolRunner slug={tool.slug} />
      ) : (
        <JobRunner tool={tool} />
      )}
      {tool.slug === "chat-with-pdf" ? <PdfChatPanel /> : null}
      {tool.slug === "website-audit" ? <WebsiteAuditHistory /> : null}
    </main>
  );
}
