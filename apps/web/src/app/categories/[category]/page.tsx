import Link from "next/link";
import { notFound } from "next/navigation";
import { clientTools } from "@/lib/client-tools";

const categories: Record<string, string> = {
  pdf: "PDF tools",
  image: "Image tools",
  "audio-video": "Audio & video tools",
  writing: "Writing tools",
  business: "Business tools",
  developer: "Developer tools",
};

type Tool = { slug: string; name: string; category: string; summary: string };

async function allTools(): Promise<Tool[]> {
  try {
    const response = await fetch(`${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/tools`, { cache: "no-store" });
    if (response.ok) return [...((await response.json()) as Tool[]), ...clientTools];
  } catch { /* The local tools can render while the API is unavailable. */ }
  return clientTools;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params;
  const title = categories[category];
  return title ? { title: `${title} | RenderCart`, description: `Browse RenderCart ${title.toLowerCase()}.` } : { title: "Category not found | RenderCart" };
}

export default async function CategoryPage({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params;
  const title = categories[category];
  if (!title) notFound();
  const tools = (await allTools()).filter((tool) => tool.category === category);
  return <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
    <Link href="/tools" className="text-sm font-medium text-violet-700 dark:text-violet-300">← All tools</Link>
    <h1 className="mt-12 text-4xl font-semibold">{title}</h1>
    <p className="mt-3 text-slate-600 dark:text-slate-300">Focused tools to help you get this part of your work done.</p>
    {tools.length ? <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{tools.map((tool) => <Link key={tool.slug} href={`/tools/${tool.slug}`} className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900"><h2 className="text-xl font-semibold">{tool.name}</h2><p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{tool.summary}</p></Link>)}</div> : <p className="mt-8 rounded-2xl border border-slate-200 p-6 text-slate-600 dark:border-slate-700">More tools in this category are on the way. <Link className="font-semibold text-violet-700 dark:text-violet-300" href="/tools">Browse all tools.</Link></p>}
  </main>;
}
