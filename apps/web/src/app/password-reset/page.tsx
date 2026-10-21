"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { authPost } from "@/lib/auth";

export default function PasswordResetPage() {
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    const data = new FormData(event.currentTarget);
    try {
      if (token) {
        await authPost("password-reset", {
          token,
          new_password: String(data.get("new_password")),
        });
        setMessage("Your password has been changed. You can sign in now.");
      } else {
        const result = await authPost<{ status: string }>("password-reset/request", {
          email: String(data.get("email")),
        });
        setMessage(result.status);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not complete the request.");
    }
  }

  return <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
    <Link href="/" className="mb-8 text-xl font-bold">RenderCart<span className="text-violet-600">.</span></Link>
    <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <h1 className="text-2xl font-semibold">{token ? "Choose a new password" : "Reset your password"}</h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{token ? "Choose a password with at least 10 characters." : "We’ll email you a one-time reset link if the account exists."}</p>
      <form className="mt-7 space-y-4" onSubmit={submit}>
        {token ? <label className="block text-sm font-medium">New password<input name="new_password" type="password" minLength={10} required autoComplete="new-password" className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2.5 dark:border-slate-600" /></label> : <label className="block text-sm font-medium">Email<input name="email" type="email" required autoComplete="email" className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2.5 dark:border-slate-600" /></label>}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        {message && <p role="status" className="text-sm text-emerald-700">{message}</p>}
        <button className="w-full rounded-xl bg-violet-600 px-4 py-3 font-medium text-white">{token ? "Save password" : "Send reset link"}</button>
      </form>
      <Link className="mt-5 inline-block text-sm text-violet-700 dark:text-violet-300" href="/login">Return to sign in</Link>
    </section>
  </main>;
}
