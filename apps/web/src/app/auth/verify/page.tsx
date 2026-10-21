"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { authPost } from "@/lib/auth";

export default function VerifyEmailPage() {
  const [status, setStatus] = useState("Verifying your email…");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setStatus("This verification link is missing its token.");
      return;
    }
    authPost("verify-email", { token })
      .then(() => setStatus("Your email is verified. You can sign in now."))
      .catch((cause: unknown) => setStatus(cause instanceof Error ? cause.message : "Could not verify your email."));
  }, []);

  return <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
    <Link href="/" className="mb-8 text-xl font-bold">RenderCart<span className="text-violet-600">.</span></Link>
    <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <h1 className="text-2xl font-semibold">Email verification</h1>
      <p role="status" className="mt-3 text-slate-600 dark:text-slate-300">{status}</p>
      <Link className="mt-5 inline-block text-sm font-medium text-violet-700 dark:text-violet-300" href="/login">Continue to sign in</Link>
    </section>
  </main>;
}
