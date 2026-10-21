"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { authPost, AuthResponse } from "@/lib/auth";

export default function LoginPage() {
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    setBusy(true);
    const data = new FormData(event.currentTarget);
    const totpCode = String(data.get("totp_code") ?? "").trim();
    try {
      await authPost<AuthResponse>("login", {
        email: String(data.get("email")),
        password: String(data.get("password")),
        ...(totpCode ? { totp_code: totpCode } : {}),
      });
      const requested = new URLSearchParams(window.location.search).get("next");
      const destination = requested?.startsWith("/") && !requested.startsWith("//") && !requested.includes("\\")
        ? requested
        : "/account";
      window.location.assign(destination);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  async function magicLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await authPost<{ status: string }>("magic-link", {
        email: String(data.get("email")),
      });
      setMessage(result.status);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not request a sign-in link.");
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
      <Link href="/" className="mb-8 text-xl font-bold">RenderCart<span className="text-violet-600">.</span></Link>
      <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <h1 className="text-2xl font-semibold">Welcome back</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Sign in to continue to your tools.</p>
        <form className="mt-7 space-y-4" onSubmit={login}>
          <label className="block text-sm font-medium">Email<input name="email" type="email" autoComplete="email" required className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2.5 dark:border-slate-600" /></label>
          <label className="block text-sm font-medium">Password<input name="password" type="password" autoComplete="current-password" required className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2.5 dark:border-slate-600" /></label>
          <label className="block text-sm font-medium">Authenticator or recovery code <span className="font-normal text-slate-500">(if enabled)</span><input name="totp_code" inputMode="numeric" autoComplete="one-time-code" className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2.5 dark:border-slate-600" /></label>
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          {message && <p role="status" className="text-sm text-emerald-700">{message}</p>}
          <button disabled={busy} className="w-full rounded-xl bg-violet-600 px-4 py-3 font-medium text-white disabled:opacity-60">{busy ? "Signing in…" : "Sign in"}</button>
        </form>
        <form className="mt-6 border-t border-slate-200 pt-5 dark:border-slate-700" onSubmit={magicLink}>
          <label className="block text-sm font-medium">Or email me a sign-in link<input name="email" type="email" required autoComplete="email" className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2.5 dark:border-slate-600" /></label>
          <button className="mt-3 w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium dark:border-slate-600">Email a sign-in link</button>
        </form>
        <div className="mt-5 grid grid-cols-2 gap-3">
          <a className="rounded-xl border border-slate-300 px-3 py-2.5 text-center text-sm dark:border-slate-600" href="/api/auth/oauth/google/start">Continue with Google</a>
          <a className="rounded-xl border border-slate-300 px-3 py-2.5 text-center text-sm dark:border-slate-600" href="/api/auth/oauth/github/start">Continue with GitHub</a>
        </div>
        <div className="mt-5 flex justify-between text-sm"><Link className="text-violet-700 dark:text-violet-300" href="/signup">Create an account</Link><Link className="text-violet-700 dark:text-violet-300" href="/password-reset">Forgot password?</Link></div>
      </section>
    </main>
  );
}
