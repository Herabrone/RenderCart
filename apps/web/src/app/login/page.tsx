"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { authPost, AuthResponse } from "@/lib/auth";

export default function LoginPage() {
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [magicBusy, setMagicBusy] = useState(false);

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
      const destination =
        requested?.startsWith("/") &&
        !requested.startsWith("//") &&
        !requested.includes("\\")
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
    if (magicBusy) return;
    setMagicBusy(true);
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
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not request a sign-in link.",
      );
    } finally {
      setMagicBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
      <section className="rounded-3xl border border-line bg-surface p-8 shadow-sm  ">
        <h1 className="text-2xl font-semibold">Welcome back</h1>
        <p className="mt-2 text-sm text-muted ">
          Sign in to continue to your tools.
        </p>
        <form className="mt-7 space-y-4" onSubmit={login}>
          <label className="block text-sm font-medium">
            Email
            <input
              name="email"
              type="email"
              autoComplete="email"
              required
              className="mt-1 w-full rounded-xl border border-line-strong bg-transparent px-3 py-2.5 "
            />
          </label>
          <label className="block text-sm font-medium">
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              className="mt-1 w-full rounded-xl border border-line-strong bg-transparent px-3 py-2.5 "
            />
          </label>
          <details className="text-sm">
            <summary className="text-muted">
              Use a two-factor or recovery code
            </summary>
            <label className="mt-3 block text-sm font-medium">
              Authenticator or recovery code
              <input
                name="totp_code"
                inputMode="text"
                autoComplete="one-time-code"
                className="mt-1 w-full rounded-xl border border-line-strong bg-transparent px-3 py-2.5 "
              />
            </label>
          </details>
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
          {message && (
            <p role="status" className="text-sm text-emerald-700">
              {message}
            </p>
          )}
          <button
            disabled={busy}
            className="w-full rounded-xl bg-accent px-4 py-3 font-medium text-white disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <details className="mt-6 border-t border-line pt-5 text-sm">
          <summary className="font-medium">Prefer a sign-in link?</summary>
          <form className="mt-4" onSubmit={magicLink}>
            <label className="block text-sm font-medium">
              Email address
              <input
                name="email"
                type="email"
                required
                autoComplete="email"
                className="mt-1 w-full rounded-xl border border-line-strong bg-transparent px-3 py-2.5 "
              />
            </label>
            <button
              disabled={magicBusy}
              className="mt-3 w-full rounded-xl border border-line-strong px-4 py-2.5 text-sm font-medium disabled:opacity-60"
            >
              {magicBusy ? "Sending…" : "Email a sign-in link"}
            </button>
          </form>
        </details>
        <div className="mt-5 grid grid-cols-2 gap-3">
          <a
            className="rounded-xl border border-line-strong px-3 py-2.5 text-center text-sm "
            href="/api/auth/oauth/google/start"
          >
            Continue with Google
          </a>
          <a
            className="rounded-xl border border-line-strong px-3 py-2.5 text-center text-sm "
            href="/api/auth/oauth/github/start"
          >
            Continue with GitHub
          </a>
        </div>
        <div className="mt-5 flex justify-between text-sm">
          <Link className="text-accent " href="/signup">
            Create an account
          </Link>
          <Link className="text-accent " href="/password-reset">
            Forgot password?
          </Link>
        </div>
      </section>
    </main>
  );
}
