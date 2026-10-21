import Link from "next/link";
import { clientTools } from "@/lib/client-tools";

type Tool = { slug: string; name: string; category: string; summary: string; seo: { title: string; description: string } };

async function getTools(): Promise<Tool[]> {
  try {
    const response = await fetch(`${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/tools`, { next: { revalidate: 300 } });
    if (response.ok) return [...((await response.json()) as Tool[]), ...clientTools];
  } catch { /* API may still be starting in local development. */ }
  return clientTools;
}

export const metadata = { title: "All Tools | RenderCart", description: "Browse PDF, image, writing, media, business, and developer tools." };
export const dynamic = "force-dynamic";

export default async function ToolsPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const [{ q }, allTools] = await Promise.all([searchParams, getTools()]);
  const query = q?.trim().toLocaleLowerCase() ?? "";
  const tools = query ? allTools.filter((tool) => `${tool.name} ${tool.summary} ${tool.category}`.toLocaleLowerCase().includes(query)) : allTools;
  return <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
    <Link href="/" className="font-bold">RenderCart</Link>
    <h1 className="mt-12 text-4xl font-semibold">All tools</h1>
    <p className="mt-3 text-slate-600 dark:text-slate-300">Practical tools for files, creative work, and everyday tasks.</p>
    <form action="/tools" className="mt-6 flex max-w-xl gap-3"><input name="q" defaultValue={q} aria-label="Search tools" className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-transparent px-4 py-3 dark:border-slate-600" placeholder="Search tools" /><button className="rounded-xl bg-violet-600 px-5 py-3 font-medium text-white">Search</button></form>
    {query && <p className="mt-5 text-sm text-slate-500">{tools.length} result{tools.length === 1 ? "" : "s"} for “{q}”</p>}
    {tools.length === 0 ? <p className="mt-10 rounded-2xl border border-slate-200 p-6 text-slate-600 dark:border-slate-700">Tools are temporarily unavailable. Please refresh in a moment.</p> : <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{tools.map((tool) => <Link key={tool.slug} href={`/tools/${tool.slug}`} className="rounded-2xl border border-slate-200 bg-white p-6 transition hover:-translate-y-1 hover:shadow-lg dark:border-slate-700 dark:bg-slate-900"><span className="text-xs font-semibold uppercase tracking-wider text-violet-600">{tool.category}</span><h2 className="mt-3 text-xl font-semibold">{tool.name}</h2><p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{tool.summary}</p></Link>)}</div>}
  </main>;
}
