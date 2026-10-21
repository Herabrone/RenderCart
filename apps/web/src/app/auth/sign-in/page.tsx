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
      setError(
        cause instanceof Error
          ? cause.message
          : "This sign-in link may be invalid or expired.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
      <section className="rounded-3xl border border-line bg-surface p-8 shadow-sm  ">
        <h1 className="text-2xl font-semibold">Sign in with your email link</h1>
        <p className="mt-2 text-sm text-muted ">
          If you use an authenticator app, enter its code or one of your
          recovery codes.
        </p>
        <form className="mt-7 space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Authenticator or recovery code
            <input
              name="totp_code"
              autoComplete="one-time-code"
              className="mt-1 w-full rounded-xl border border-line-strong bg-transparent px-3 py-2.5 "
            />
          </label>
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
          <button
            disabled={!token || busy}
            className="w-full rounded-xl bg-accent px-4 py-3 font-medium text-white disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Continue"}
          </button>
        </form>
        <Link href="/login" className="mt-5 inline-block text-sm text-accent ">
          Return to sign in
        </Link>
      </section>
    </main>
  );
}
