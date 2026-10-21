import { ArrowRight, FileText, Image, WandSparkles } from "lucide-react";
import Link from "next/link";

const categories = [
  { name: "PDF tools", category: "pdf", text: "Merge, convert, organize, and protect documents.", icon: FileText },
  { name: "Image studio", category: "image", text: "Resize, convert, compress, and enhance images.", icon: Image },
  { name: "Audio & video", category: "audio-video", text: "Turn media files into useful results.", icon: WandSparkles },
];

export default function Home() {
  return (
    <main className="mx-auto min-h-screen max-w-7xl px-6 py-8 sm:px-10">
      <header className="flex items-center justify-between">
        <Link className="text-xl font-bold tracking-tight" href="/">RenderCart<span className="text-violet-600">.</span></Link>
        <nav className="flex items-center gap-6 text-sm text-slate-600 dark:text-slate-300">
          <a href="#tools">Explore tools</a><Link href="/pricing">Pricing</Link><Link className="rounded-full bg-slate-900 px-4 py-2 font-medium text-white dark:bg-white dark:text-slate-900" href="/login">Sign in</Link>
        </nav>
      </header>
      <section className="py-24 text-center sm:py-32">
        <p className="mb-5 inline-flex rounded-full border border-violet-200 bg-violet-50 px-4 py-1.5 text-sm font-medium text-violet-800 dark:border-violet-900 dark:bg-violet-950 dark:text-violet-200">A little toolbox for a lot of things</p>
        <h1 className="mx-auto max-w-4xl text-5xl font-semibold tracking-tight sm:text-7xl">Everything useful, <span className="text-violet-600">in one place.</span></h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-slate-600 dark:text-slate-300">Simple tools for your files, creative work, business, and everyday tasks. Start with the tools you need, and keep moving.</p>
        <form action="/tools" className="mx-auto mt-10 flex max-w-xl gap-3 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <input name="q" aria-label="Search tools" className="min-w-0 flex-1 bg-transparent px-4 outline-none" placeholder="What do you need to do?" />
          <button className="rounded-xl bg-violet-600 px-5 py-3 font-medium text-white">Find a tool</button>
        </form>
        <p className="mt-4 text-sm text-slate-500">Popular: merge PDF · image converter · word counter</p>
      </section>
      <section id="tools" className="pb-20">
        <div className="mb-8 flex items-end justify-between"><div><p className="text-sm font-semibold uppercase tracking-widest text-violet-600">Explore</p><h2 className="mt-2 text-3xl font-semibold">Tools for your day</h2></div><Link className="flex items-center gap-2 text-sm font-medium" href="/tools">Browse all <ArrowRight size={16} /></Link></div>
        <div className="grid gap-4 md:grid-cols-3">{categories.map(({ name, category, text, icon: Icon }) => <Link key={name} className="group rounded-2xl border border-slate-200 bg-white p-6 transition hover:-translate-y-1 hover:shadow-lg dark:border-slate-700 dark:bg-slate-900" href={`/categories/${category}`}><span className="mb-8 inline-flex rounded-xl bg-violet-100 p-3 text-violet-700 dark:bg-violet-950 dark:text-violet-200"><Icon size={22} /></span><h3 className="text-xl font-semibold">{name}</h3><p className="mt-2 min-h-12 text-slate-600 dark:text-slate-300">{text}</p><span className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-violet-700 dark:text-violet-300">Explore category <ArrowRight size={15} className="transition group-hover:translate-x-1" /></span></Link>)}</div>
      </section>
      <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-200 py-6 text-sm text-slate-500 dark:border-slate-800">
        <span>© {new Date().getFullYear()} RenderCart · Useful tools, thoughtfully made.</span>
        <nav aria-label="Legal" className="flex flex-wrap gap-x-4 gap-y-2">
          <Link href="/legal/terms">Terms</Link>
          <Link href="/legal/privacy">Privacy</Link>
          <Link href="/legal/acceptable-use">Acceptable use</Link>
          <Link href="/legal/dmca">Copyright</Link>
          <Link href="/legal/refunds">Refunds</Link>
        </nav>
      </footer>
    </main>
  );
}
