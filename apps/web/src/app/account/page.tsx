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

  function openWorkspaceSection(event: React.MouseEvent<HTMLAnchorElement>) {
    const element = document.getElementById(event.currentTarget.hash.slice(1));
    if (element instanceof HTMLDetailsElement) element.open = true;
  }

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
    <main className="account-page">
      <header className="account-overview">
        <div>
          <span className="eyebrow">Your workspace</span>
          <h1 className="mt-3 text-4xl font-semibold">
            A place for your work.
          </h1>
        </div>

        <button
          onClick={logout}
          className="rounded-xl border border-line-strong px-4 py-2 text-sm "
        >
          Sign out
        </button>
      </header>
      <section className="account-dashboard rounded-3xl border border-line bg-surface p-8">
        <h2 className="text-xl font-semibold">Your account</h2>
        {user ? (
          <div className="account-profile">
            <span className="profile-avatar" aria-hidden="true">
              {(user.display_name || user.email).slice(0, 1).toUpperCase()}
            </span>
            <div>
              <p className="font-semibold">{user.display_name || user.email}</p>
              <p className="profile-status">
                {user.email} ·{" "}
                {user.email_verified ? "Verified" : "Email verification needed"}
              </p>
            </div>
          </div>
        ) : (
          <p role={error ? "alert" : "status"} className="mt-5 text-muted ">
            {error || "Loading account…"}
            {error && (
              <Link
                className="button button-primary mt-4"
                href="/login?next=/account"
              >
                Sign in
              </Link>
            )}
          </p>
        )}
        {user && user.staff_role !== "user" && (
          <Link
            href="/admin"
            className="mt-4 inline-block text-sm font-semibold text-accent "
          >
            Open admin dashboard
          </Link>
        )}
        {user && (
          <>
            <nav className="management-tabs" aria-label="Workspace sections">
              <a href="#api-keys" onClick={openWorkspaceSection}>
                API keys
              </a>
              <a href="#monitors" onClick={openWorkspaceSection}>
                Monitors
              </a>
              <a href="#domains" onClick={openWorkspaceSection}>
                Domain alerts
              </a>
              <a href="#request-bins" onClick={openWorkspaceSection}>
                Request bins
              </a>
              <a href="#security">Security</a>
              <a href="#recent-jobs">Recent jobs</a>
              <Link href="/account/billing">Billing & credits ↗</Link>
            </nav>
            <details id="api-keys">
              <summary>API keys</summary>
              <div>
                <ApiKeyManager />
              </div>
            </details>
          </>
        )}
        {user && (
          <details id="monitors">
            <summary>Website monitors</summary>
            <div>
              <MonitorManager />
            </div>
          </details>
        )}
        {user && (
          <details id="domains">
            <summary>Domain & SSL alerts</summary>
            <div>
              <DomainAlertManager />
            </div>
          </details>
        )}
        {user && (
          <details id="request-bins">
            <summary>Webhook request bins</summary>
            <div>
              <WebhookBinManager />
            </div>
          </details>
        )}
        {user && (
          <section id="security" className="mt-8 border-t border-line pt-6">
            <h2 className="text-lg font-semibold">Security</h2>
            {user.totp_enabled && (
              <p className="mt-3 text-sm text-muted">
                Two-factor authentication is enabled
                {user.mfa_verified
                  ? ". This session is verified."
                  : "; verify this session below."}
              </p>
            )}
            {user && !user.totp_enabled && (
              <div className="mt-4">
                <h2 className="text-lg font-semibold">
                  Two-factor authentication
                </h2>
                <p className="mt-1 text-sm text-muted ">
                  Protect your account with an authenticator app. Staff accounts
                  need this enabled for admin access.
                </p>
                <button
                  onClick={startTotp}
                  className="mt-4 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white"
                >
                  Set up authenticator
                </button>
              </div>
            )}
            {setup && (
              <div className="mt-6 rounded-2xl bg-canvas p-5 ">
                <h3 className="font-semibold">
                  Add this account to your authenticator
                </h3>
                <p className="mt-2 break-all font-mono text-sm">
                  {setup.secret}
                </p>
                <p className="mt-2 break-all text-xs text-muted">
                  {setup.provisioning_uri}
                </p>
                <form
                  onSubmit={confirmTotp}
                  className="mt-4 flex flex-wrap gap-3"
                >
                  <input
                    name="code"
                    required
                    minLength={6}
                    maxLength={64}
                    autoComplete="one-time-code"
                    placeholder="Authenticator code"
                    className="min-w-0 flex-1 rounded-xl border border-line-strong bg-transparent px-3 py-2 "
                  />
                  <button className="rounded-xl bg-accent px-4 py-2 font-medium text-white">
                    Confirm setup
                  </button>
                </form>
              </div>
            )}
            {user?.totp_enabled && !user.mfa_verified && (
              <form
                onSubmit={verifyTotp}
                className="mt-6 rounded-2xl bg-amber-50 p-5 "
              >
                <h2 className="font-semibold">Verify your second factor</h2>
                <p className="mt-1 text-sm">
                  Enter an authenticator or recovery code to unlock staff
                  access.
                </p>
                <div className="mt-3 flex flex-wrap gap-3">
                  <input
                    name="code"
                    required
                    minLength={6}
                    maxLength={64}
                    autoComplete="one-time-code"
                    placeholder="Authenticator or recovery code"
                    className="min-w-0 flex-1 rounded-xl border border-line-strong bg-transparent px-3 py-2 "
                  />
                  <button className="rounded-xl bg-accent px-4 py-2 font-medium text-white">
                    Verify
                  </button>
                </div>
              </form>
            )}
            {recoveryCodes.length > 0 && (
              <div
                role="alert"
                className="mt-6 rounded-2xl border border-amber-400 bg-amber-50 p-5 "
              >
                <h2 className="font-semibold">Save your recovery codes</h2>
                <p className="mt-1 text-sm">
                  Each code works once. Store them somewhere safe; they will not
                  be shown again.
                </p>
                <ul className="mt-3 grid grid-cols-2 gap-2 font-mono text-sm">
                  {recoveryCodes.map((code) => (
                    <li key={code}>{code}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
        {user && (
          <div className="mt-8 border-t border-line pt-6 ">
            <h2 id="recent-jobs" className="text-lg font-semibold">
              Recent jobs
            </h2>
            {jobs.length === 0 ? (
              <p className="mt-3 text-sm text-muted">
                Your completed and active jobs will appear here.{" "}
                <Link href="/tools" className="text-accent underline">
                  Find a tool to get started.
                </Link>
              </p>
            ) : (
              <ul className="mt-4 divide-y divide-line ">
                {jobs.map((job) => (
                  <li
                    key={job.job_id}
                    className="flex flex-wrap items-center justify-between gap-3 py-4"
                  >
                    <div>
                      <Link
                        className="font-medium text-accent "
                        href={`/jobs/${job.job_id}`}
                      >
                        {job.tool_slug.replaceAll("-", " ")}
                      </Link>
                      <p className="mt-1 text-xs text-muted">
                        {job.created_at
                          ? new Date(job.created_at).toLocaleString()
                          : ""}{" "}
                        · {job.state}
                      </p>
                    </div>
                    {job.download_url && (
                      <a
                        className="rounded-lg border border-line-strong px-3 py-2 text-sm "
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
