import Link from "next/link";

export const metadata = { title: "Pricing | RenderCart", description: "Choose free access, a day pass, or RenderCart Pro." };

export default function PricingPage() {
  return <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
    <Link href="/" className="font-bold">RenderCart</Link>
    <header className="mx-auto mt-16 max-w-2xl text-center"><p className="text-sm font-semibold uppercase tracking-widest text-violet-600">Simple pricing</p><h1 className="mt-3 text-4xl font-semibold">Start free. Upgrade when you need more.</h1><p className="mt-4 text-slate-600 dark:text-slate-300">Free daily limits stay available. Paid access removes limits and unlocks higher file sizes.</p></header>
    <div className="mx-auto mt-10 grid max-w-5xl gap-5 md:grid-cols-3">
      <article className="rounded-3xl border border-slate-200 bg-white p-7 dark:border-slate-700 dark:bg-slate-900"><h2 className="text-xl font-semibold">Free</h2><p className="mt-3 text-4xl font-bold">$0</p><p className="mt-3 min-h-12 text-sm text-slate-600 dark:text-slate-300">A few jobs each day with starter file limits.</p><Link className="mt-7 inline-block rounded-xl border border-slate-300 px-4 py-3 text-sm font-semibold dark:border-slate-600" href="/tools">Browse free tools</Link></article>
      <article className="rounded-3xl border-2 border-violet-500 bg-white p-7 shadow-lg dark:bg-slate-900"><p className="text-sm font-semibold text-violet-600">Best value</p><h2 className="mt-2 text-xl font-semibold">Pro</h2><p className="mt-3 text-4xl font-bold">$9.99<span className="text-base font-normal text-slate-500"> / month</span></p><p className="mt-3 min-h-12 text-sm text-slate-600 dark:text-slate-300">All public tools, higher limits, and 1,000 monthly credits.</p><Link className="mt-7 inline-block rounded-xl bg-violet-600 px-4 py-3 text-sm font-semibold text-white" href="/account/billing">Get Pro</Link></article>
      <article className="rounded-3xl border border-slate-200 bg-white p-7 dark:border-slate-700 dark:bg-slate-900"><h2 className="text-xl font-semibold">Day pass</h2><p className="mt-3 text-4xl font-bold">$2.99<span className="text-base font-normal text-slate-500"> / day</span></p><p className="mt-3 min-h-12 text-sm text-slate-600 dark:text-slate-300">Short-term access for a busy day of work.</p><Link className="mt-7 inline-block rounded-xl border border-slate-300 px-4 py-3 text-sm font-semibold dark:border-slate-600" href="/account/billing">Buy a day pass</Link></article>
    </div>
    <p className="mx-auto mt-8 max-w-3xl text-center text-sm text-slate-500">Single jobs are available at $0.99, $1.99, or $2.99 depending on the tool. Checkout opens from your account billing page.</p>
  </main>;
}
