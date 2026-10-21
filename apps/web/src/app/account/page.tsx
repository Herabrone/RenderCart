"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { authPost, AuthResponse } from "@/lib/auth";
import { ApiKeyManager } from "@/lib/api-key-manager";
import { MonitorManager } from "@/lib/monitor-manager";
import { DomainAlertManager } from "@/lib/domain-alert-manager";
import { WebhookBinManager } from "@/lib/webhook-bin-manager";

type TotpSetup = { secret: string; provisioning_uri: string };
type JobHistory = {
  job_id: string;
  tool_slug: string;
  state: string;
  created_at: string | null;
  download_url: string | null;
};

export default function AccountPage() {
  const [user, setUser] = useState<AuthResponse | null>(null);
  const [error, setError] = useState("");
  const [setup, setSetup] = useState<TotpSetup | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [jobs, setJobs] = useState<JobHistory[]>([]);

  const loadUser = useCallback(async () => {
    const response = await fetch("/api/auth/me", { credentials: "include" });
    if (!response.ok) throw new Error("Please sign in to view your account.");
    setUser((await response.json()) as AuthResponse);
    const jobResponse = await fetch("/api/jobs?limit=30", {
      credentials: "include",
      cache: "no-store",
    });
    if (jobResponse.ok) setJobs((await jobResponse.json()) as JobHistory[]);
  }, []);

  useEffect(() => {
    loadUser().catch((cause: unknown) =>
      setError(
        cause instanceof Error ? cause.message : "Could not load account.",
      ),
    );
  }, [loadUser]);

  async function logout() {
    try {
      await authPost("logout", {});
      window.location.assign("/login");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign out.");
    }
  }

  async function startTotp() {
    setError("");
    try {
      setSetup(await authPost<TotpSetup>("totp/setup", {}));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not start authenticator setup.",
      );
    }
  }

  async function confirmTotp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = String(new FormData(event.currentTarget).get("code"));
    try {
      const result = await authPost<{ recovery_codes: string[] }>(
        "totp/confirm",
        { code },
      );
      setRecoveryCodes(result.recovery_codes);
      setSetup(null);
      await loadUser();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not verify that code.",
      );
    }
  }

  async function verifyTotp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = String(new FormData(event.currentTarget).get("code"));
    try {
      await authPost("totp/verify", { code });
      await loadUser();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not verify that code.",
      );
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-6 py-10">
      <header className="flex items-center justify-between">
        <Link href="/" className="text-xl font-bold">
          RenderCart<span className="text-violet-600">.</span>
        </Link>
        <button
          onClick={logout}
          className="rounded-xl border border-slate-300 px-4 py-2 text-sm dark:border-slate-600"
        >
          Sign out
        </button>
      </header>
      <section className="mt-16 rounded-3xl border border-slate-200 bg-white p-8 dark:border-slate-700 dark:bg-slate-900">
        <h1 className="text-3xl font-semibold">Your account</h1>
        {user ? (
          <div className="mt-5 space-y-2 text-slate-600 dark:text-slate-300">
            <p>{user.display_name || user.email}</p>
            <p>
              {user.email_verified ? "Email verified" : "Email not verified"}
            </p>
            <p>Role: {user.staff_role}</p>
          </div>
        ) : (
          <p
            role={error ? "alert" : "status"}
            className="mt-5 text-slate-600 dark:text-slate-300"
          >
            {error || "Loading account…"}
          </p>
        )}
        {user && user.staff_role !== "user" && (
          <Link
            href="/admin"
            className="mt-4 inline-block text-sm font-semibold text-violet-700 dark:text-violet-300"
          >
            Open admin dashboard
          </Link>
        )}
        {user && <ApiKeyManager />}
        {user && <MonitorManager />}
        {user && <DomainAlertManager />}
        {user && <WebhookBinManager />}
        {user && !user.totp_enabled && (
          <div className="mt-8 border-t border-slate-200 pt-6 dark:border-slate-700">
            <h2 className="text-lg font-semibold">Two-factor authentication</h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              Protect your account with an authenticator app. Staff accounts
              need this enabled for admin access.
            </p>
            <button
              onClick={startTotp}
              className="mt-4 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-medium text-white"
            >
              Set up authenticator
            </button>
          </div>
        )}
        {setup && (
          <div className="mt-6 rounded-2xl bg-slate-50 p-5 dark:bg-slate-800">
            <h3 className="font-semibold">
              Add this account to your authenticator
            </h3>
            <p className="mt-2 break-all font-mono text-sm">{setup.secret}</p>
            <p className="mt-2 break-all text-xs text-slate-500">
              {setup.provisioning_uri}
            </p>
            <form onSubmit={confirmTotp} className="mt-4 flex flex-wrap gap-3">
              <input
                name="code"
                required
                minLength={6}
                maxLength={64}
                autoComplete="one-time-code"
                placeholder="Authenticator code"
                className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
              />
              <button className="rounded-xl bg-violet-600 px-4 py-2 font-medium text-white">
                Confirm setup
              </button>
            </form>
          </div>
        )}
        {user?.totp_enabled && !user.mfa_verified && (
          <form
            onSubmit={verifyTotp}
            className="mt-6 rounded-2xl bg-amber-50 p-5 dark:bg-amber-950"
          >
            <h2 className="font-semibold">Verify your second factor</h2>
            <p className="mt-1 text-sm">
              Enter an authenticator or recovery code to unlock staff access.
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              <input
                name="code"
                required
                minLength={6}
                maxLength={64}
                autoComplete="one-time-code"
                placeholder="Authenticator or recovery code"
                className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
              />
              <button className="rounded-xl bg-violet-600 px-4 py-2 font-medium text-white">
                Verify
              </button>
            </div>
          </form>
        )}
        {recoveryCodes.length > 0 && (
          <div
            role="alert"
            className="mt-6 rounded-2xl border border-amber-400 bg-amber-50 p-5 dark:bg-amber-950"
          >
            <h2 className="font-semibold">Save your recovery codes</h2>
            <p className="mt-1 text-sm">
              Each code works once. Store them somewhere safe; they will not be
              shown again.
            </p>
            <ul className="mt-3 grid grid-cols-2 gap-2 font-mono text-sm">
              {recoveryCodes.map((code) => (
                <li key={code}>{code}</li>
              ))}
            </ul>
          </div>
        )}
        {user && (
          <div className="mt-8 border-t border-slate-200 pt-6 dark:border-slate-700">
            <h2 className="text-lg font-semibold">Recent jobs</h2>
            {jobs.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">
                Your completed and active jobs will appear here.
              </p>
            ) : (
              <ul className="mt-4 divide-y divide-slate-200 dark:divide-slate-700">
                {jobs.map((job) => (
                  <li
                    key={job.job_id}
                    className="flex flex-wrap items-center justify-between gap-3 py-4"
                  >
                    <div>
                      <Link
                        className="font-medium text-violet-700 dark:text-violet-300"
                        href={`/jobs/${job.job_id}`}
                      >
                        {job.tool_slug.replaceAll("-", " ")}
                      </Link>
                      <p className="mt-1 text-xs text-slate-500">
                        {job.created_at
                          ? new Date(job.created_at).toLocaleString()
                          : ""}{" "}
                        · {job.state}
                      </p>
                    </div>
                    {job.download_url && (
                      <a
                        className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600"
                        href={job.download_url}
                      >
                        Download
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {error && user && (
          <p role="alert" className="mt-5 text-sm text-red-600">
            {error}
          </p>
        )}
      </section>
    </main>
  );
}
