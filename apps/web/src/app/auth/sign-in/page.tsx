"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { authPost, AuthResponse } from "@/lib/auth";

export default function MagicSignInPage() {
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const data = new FormData(event.currentTarget);
    const code = String(data.get("totp_code") ?? "").trim();
    try {
      await authPost<AuthResponse>("magic", {
        token,
        ...(code ? { totp_code: code } : {}),
      });
      window.location.assign("/account");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "This sign-in link may be invalid or expired.");
    } finally {
      setBusy(false);
    }
  }

  return <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
    <Link href="/" className="mb-8 text-xl font-bold">RenderCart<span className="text-violet-600">.</span></Link>
    <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <h1 className="text-2xl font-semibold">Sign in with your email link</h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">If you use an authenticator app, enter its code or one of your recovery codes.</p>
      <form className="mt-7 space-y-4" onSubmit={submit}>
        <label className="block text-sm font-medium">Authenticator or recovery code<input name="totp_code" autoComplete="one-time-code" className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2.5 dark:border-slate-600" /></label>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button disabled={!token || busy} className="w-full rounded-xl bg-violet-600 px-4 py-3 font-medium text-white disabled:opacity-60">{busy ? "Signing in…" : "Continue"}</button>
      </form>
      <Link href="/login" className="mt-5 inline-block text-sm text-violet-700 dark:text-violet-300">Return to sign in</Link>
    </section>
  </main>;
}
