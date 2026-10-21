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
      .catch((cause: unknown) =>
        setStatus(
          cause instanceof Error
            ? cause.message
            : "Could not verify your email.",
        ),
      );
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
      <section className="rounded-3xl border border-line bg-surface p-8 shadow-sm  ">
        <h1 className="text-2xl font-semibold">Email verification</h1>
        <p role="status" className="mt-3 text-muted ">
          {status}
        </p>
        <Link
          className="mt-5 inline-block text-sm font-medium text-accent "
          href="/login"
        >
          Continue to sign in
        </Link>
      </section>
    </main>
  );
}
