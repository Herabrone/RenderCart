"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type BillingStatus = {
  level: string;
  credits: number;
  subscription: {
    status: string;
    current_period_end: string | null;
    cancel_at_period_end: boolean;
  } | null;
  day_pass_ends_at: string | null;
};

export default function BillingPage() {
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [guestEmail, setGuestEmail] = useState("");

  const load = useCallback(async () => {
    const response = await fetch("/api/billing/status", { credentials: "include", cache: "no-store" });
    if (response.status === 401 || response.status === 403) {
      setSignedIn(false);
      return;
    }
    if (!response.ok) throw new Error("Could not load billing details.");
    setBilling((await response.json()) as BillingStatus);
    setSignedIn(true);
  }, []);

  useEffect(() => {
    load().catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : "Could not load billing details."));
  }, [load]);

  async function post(path: string, body?: object) {
    setBusy(true);
    setMessage("");
    try {
      const csrf = await fetch("/api/auth/csrf", { credentials: "include" });
      if (!csrf.ok) throw new Error("Please sign in again before changing billing.");
      const { csrf_token: csrfToken } = (await csrf.json()) as { csrf_token: string };
      const response = await fetch(`/api/billing/${path}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-RC-CSRF": csrfToken },
        body: JSON.stringify(body ?? {}),
      });
      const payload = (await response.json()) as { url?: string; detail?: string };
      if (!response.ok) throw new Error(payload.detail ?? "Billing request failed.");
      if (!payload.url) throw new Error("Stripe did not return a destination URL.");
      window.location.assign(payload.url);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Billing request failed.");
    } finally {
      setBusy(false);
    }
  }

  return <main className="mx-auto min-h-screen max-w-4xl px-6 py-10">
    <Link href="/" className="text-xl font-bold">RenderCart<span className="text-violet-600">.</span></Link>
    <section className="mt-12 rounded-3xl border border-slate-200 bg-white p-8 dark:border-slate-700 dark:bg-slate-900">
      <h1 className="text-3xl font-semibold">Billing and credits</h1>
      {signedIn === false ? <div className="mt-5 space-y-4"><p className="text-slate-600 dark:text-slate-300">Sign in to view your plan and manage purchases. <Link href="/login?next=/account/billing" className="font-semibold text-violet-700">Sign in</Link></p><div className="rounded-2xl bg-slate-50 p-5 dark:bg-slate-800"><h2 className="font-semibold">Buy a day pass as a guest</h2><p className="mt-1 text-sm text-slate-600 dark:text-slate-300">We’ll email you a one-time sign-in link to claim the pass after payment. If you have just paid, check your inbox for that link.</p><div className="mt-4 flex flex-wrap gap-3"><input aria-label="Email for day pass" type="email" autoComplete="email" required value={guestEmail} onChange={(event) => setGuestEmail(event.target.value)} placeholder="you@example.com" className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"/><button disabled={busy || !guestEmail.includes("@")} onClick={() => post("checkout", { product: "day_pass", email: guestEmail })} className="rounded-xl bg-violet-600 px-5 py-3 font-semibold text-white disabled:opacity-50">Continue to Stripe · $2.99</button></div></div></div> : null}
      {billing ? <>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl bg-slate-50 p-5 dark:bg-slate-800"><p className="text-sm text-slate-500">Current access</p><p className="mt-1 text-2xl font-semibold capitalize">{billing.level.replaceAll("_", " ")}</p></div>
          <div className="rounded-2xl bg-slate-50 p-5 dark:bg-slate-800"><p className="text-sm text-slate-500">Available credits</p><p className="mt-1 text-2xl font-semibold">{billing.credits.toLocaleString()}</p></div>
        </div>
        {billing.subscription && <p className="mt-5 text-sm text-slate-600 dark:text-slate-300">Subscription: {billing.subscription.status}{billing.subscription.current_period_end ? ` · renews/ends ${new Date(billing.subscription.current_period_end).toLocaleDateString()}` : ""}{billing.subscription.cancel_at_period_end ? " · cancellation scheduled" : ""}</p>}
        {billing.day_pass_ends_at && <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Day pass ends {new Date(billing.day_pass_ends_at).toLocaleString()}.</p>}
        <div className="mt-8 flex flex-wrap gap-3">
          <button disabled={busy || billing.level === "pro" || billing.level === "admin" || billing.level === "super_admin"} onClick={() => post("checkout", { product: "pro_monthly" })} className="rounded-xl bg-violet-600 px-5 py-3 font-semibold text-white disabled:opacity-50">Get Pro · $9.99/month</button>
          <button disabled={busy} onClick={() => post("checkout", { product: "day_pass" })} className="rounded-xl border border-slate-300 px-5 py-3 font-semibold disabled:opacity-50 dark:border-slate-600">Buy a day pass · $2.99</button>
          <button disabled={busy} onClick={() => post("checkout", { product: "credits_500" })} className="rounded-xl border border-slate-300 px-5 py-3 font-semibold disabled:opacity-50 dark:border-slate-600">Buy 500 credits · $4.99</button>
          <button disabled={busy || !billing.subscription} onClick={() => post("portal")} className="rounded-xl border border-slate-300 px-5 py-3 font-semibold disabled:opacity-50 dark:border-slate-600">Manage subscription</button>
        </div>
      </> : signedIn !== false && <p role="status" className="mt-4 text-slate-600 dark:text-slate-300">Loading billing…</p>}
      {message && <p role="alert" className="mt-5 text-sm text-red-600">{message}</p>}
      <p className="mt-8 text-sm text-slate-500">Payments open in Stripe Checkout. Access changes only after RenderCart receives and verifies Stripe’s payment notification.</p>
    </section>
  </main>;
}
