"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

type Overview = {
  actor_role: string;
  users: number;
  jobs_total: number;
  jobs_queued: number;
  jobs_running: number;
  gross_revenue_cents: number;
  ai_estimated_cost_usd_month: string;
};
type GpuHealth = {
  workers: {
    status: "online" | "offline" | "unknown";
    workers_seen: number;
    gpu_workers: string[];
    queue_depths: Record<string, number>;
    queue_depth_total: number | null;
    error: string | null;
  };
  hardware: {
    status: "online" | "unconfigured" | "no_gpu_samples" | "unavailable";
    devices: Array<Record<string, string | number>>;
  };
};
type UserRow = {
  id: string;
  email: string;
  display_name: string | null;
  staff_role: string;
  level: string;
  is_banned: boolean;
  email_verified: boolean;
  created_at: string;
};
type JobRow = {
  job_id: string;
  user_id: string | null;
  tool_slug: string;
  state: string;
  progress: number;
  error_code: string | null;
  created_at: string | null;
};
type ToolRow = {
  slug: string;
  name: string;
  enabled: boolean;
  limits: Record<string, unknown>;
  prices: Record<string, number>;
  job_tier: "S" | "M" | "L" | null;
  single_job_price_cents: number | null;
};
type AuditRow = {
  id: string;
  actor_user_id: string | null;
  action: string;
  target: string | null;
  details: Record<string, unknown>;
  created_at: string;
};
type AbuseReportRow = {
  id: string;
  qr_id: string | null;
  code: string;
  target_url: string;
  message: string | null;
  status: "open" | "resolved";
  resolved_at: string | null;
  created_at: string;
};

async function adminRequest(
  path: string,
  method: "PATCH" | "POST" | "PUT",
  body: object,
) {
  const csrfResponse = await fetch("/api/auth/csrf", {
    credentials: "include",
  });
  if (!csrfResponse.ok) throw new Error("Could not start a secure request.");
  const { csrf_token: csrf } = (await csrfResponse.json()) as {
    csrf_token: string;
  };
  const response = await fetch(path, {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-RC-CSRF": csrf },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(data.detail || "The admin action failed.");
  }
  return response.status === 204 ? null : response.json();
}

export default function AdminPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [gpuHealth, setGpuHealth] = useState<GpuHealth | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [tools, setTools] = useState<ToolRow[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [reports, setReports] = useState<AbuseReportRow[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const [responses, reportsResponse] = await Promise.all([
      Promise.all(
        [
          "overview",
          "gpu",
          "users?limit=50",
          "jobs?limit=50",
          "tools",
          "audit?limit=100",
        ].map((path) =>
          fetch(`/api/admin/${path}`, {
            credentials: "include",
            cache: "no-store",
          }),
        ),
      ),
      fetch("/api/business/dynamic-qr/admin/reports", {
        credentials: "include",
        cache: "no-store",
      }),
    ]);
    if (responses.some((response) => !response.ok) || !reportsResponse.ok) {
      throw new Error(
        "Admin access requires an admin account with a verified authenticator session.",
      );
    }
    const [summary, gpu, userRows, jobRows, toolRows, auditRows] =
      (await Promise.all(responses.map((response) => response.json()))) as [
        Overview,
        GpuHealth,
        UserRow[],
        JobRow[],
        ToolRow[],
        AuditRow[],
      ];
    const reportRows = (await reportsResponse.json()) as AbuseReportRow[];
    setOverview(summary);
    setGpuHealth(gpu);
    setUsers(userRows);
    setJobs(jobRows);
    setTools(toolRows);
    setAudit(auditRows);
    setReports(reportRows);
  }, []);

  useEffect(() => {
    void load().catch((cause: unknown) =>
      setError(
        cause instanceof Error ? cause.message : "Could not load admin data.",
      ),
    );
  }, [load]);

  async function searchUsers(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const response = await fetch(
        `/api/admin/users?q=${encodeURIComponent(query)}&limit=100`,
        {
          credentials: "include",
          cache: "no-store",
        },
      );
      if (!response.ok) throw new Error("Could not search users.");
      setUsers((await response.json()) as UserRow[]);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not search users.",
      );
    }
  }

  async function toggleBan(user: UserRow) {
    try {
      await adminRequest(`/api/admin/users/${user.id}/ban`, "PATCH", {
        banned: !user.is_banned,
      });
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not update user.",
      );
    }
  }

  async function grantCredits(user: UserRow) {
    try {
      await adminRequest(`/api/admin/users/${user.id}/credits`, "POST", {
        amount: 10,
        reason: "Admin support grant",
      });
      setError(`Granted 10 credits to ${user.email}.`);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not grant credits.",
      );
    }
  }

  async function toggleRole(user: UserRow) {
    try {
      await adminRequest(`/api/admin/users/${user.id}/role`, "PATCH", {
        role: user.staff_role === "admin" ? "user" : "admin",
      });
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Role changes require super admin access.",
      );
    }
  }

  async function toggleTool(tool: ToolRow) {
    try {
      await adminRequest(`/api/admin/tools/${tool.slug}`, "PUT", {
        enabled: !tool.enabled,
      });
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not update tool.",
      );
    }
  }

  async function saveToolPrice(event: FormEvent<HTMLFormElement>, tool: ToolRow) {
    event.preventDefault();
    const cents = Number(new FormData(event.currentTarget).get("price_cents"));
    if (!Number.isInteger(cents) || cents < 1 || !tool.job_tier) {
      setError("Enter a positive price in cents.");
      return;
    }
    try {
      await adminRequest(`/api/admin/tools/${tool.slug}`, "PUT", {
        prices: { [`job_${tool.job_tier.toLowerCase()}`]: cents },
      });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update price.");
    }
  }

  async function setReportResolved(report: AbuseReportRow, resolved: boolean) {
    try {
      await adminRequest(
        `/api/business/dynamic-qr/admin/reports/${report.id}`,
        "PATCH",
        { resolved },
      );
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update report.");
    }
  }

  async function disableReportedCode(report: AbuseReportRow) {
    if (!report.qr_id) return;
    try {
      await adminRequest(
        `/api/business/dynamic-qr/admin/${report.qr_id}/disable`,
        "POST",
        {},
      );
      setError(`Dynamic QR code ${report.code} was disabled.`);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not disable QR code.");
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-6 py-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link href="/" className="text-sm font-semibold text-violet-700">
            ← RenderCart
          </Link>
          <h1 className="mt-2 text-3xl font-semibold">Admin dashboard</h1>
        </div>
        <Link href="/account" className="text-sm font-semibold">
          Account
        </Link>
      </header>
      {error && (
        <p
          role="status"
          className="mt-5 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100"
        >
          {error}
        </p>
      )}
      {!overview ? (
        <p className="mt-8 text-sm text-slate-500">
          {error ? "Dashboard unavailable." : "Loading dashboard…"}
        </p>
      ) : (
        <>
          <section className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[
              ["Users", overview.users.toLocaleString()],
              ["Jobs", overview.jobs_total.toLocaleString()],
              [
                "Queued / running",
                `${overview.jobs_queued} / ${overview.jobs_running}`,
              ],
              [
                "Gross revenue",
                `$${(overview.gross_revenue_cents / 100).toFixed(2)}`,
              ],
              [
                "AI cost this month",
                `$${overview.ai_estimated_cost_usd_month}`,
              ],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900"
              >
                <p className="text-sm text-slate-500">{label}</p>
                <p className="mt-2 text-2xl font-semibold">{value}</p>
              </div>
            ))}
          </section>
          {gpuHealth && (
            <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-xl font-semibold">GPU workers</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Worker status and queued GPU jobs; hardware readings require a private DCGM exporter URL.
                  </p>
                </div>
                <p className="text-sm font-medium">
                  {gpuHealth.workers.status} · {gpuHealth.workers.gpu_workers.length} GPU worker(s)
                  {gpuHealth.workers.queue_depth_total === null
                    ? " · queue depth unavailable"
                    : ` · ${gpuHealth.workers.queue_depth_total} queued`}
                </p>
              </div>
              <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                {Object.entries(gpuHealth.workers.queue_depths).map(([queue, depth]) => (
                  <div key={queue} className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800">
                    <p className="text-xs text-slate-500">{queue}</p>
                    <p className="mt-1 font-semibold">{depth} waiting</p>
                  </div>
                ))}
              </div>
              <div className="mt-5">
                <h3 className="font-medium">Hardware telemetry · {gpuHealth.hardware.status}</h3>
                {gpuHealth.hardware.devices.length ? (
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full min-w-[560px] text-left text-sm">
                      <thead className="text-xs uppercase text-slate-500">
                        <tr><th className="py-2">Device</th><th>GPU use</th><th>VRAM used</th><th>Temperature</th><th>Power</th></tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                        {gpuHealth.hardware.devices.map((device) => (
                          <tr key={String(device.device)}>
                            <td className="py-2">{String(device.name)} · {String(device.device)}</td>
                            <td>{device.utilization_percent === undefined ? "—" : `${device.utilization_percent}%`}</td>
                            <td>{device.memory_used_mib === undefined ? "—" : `${device.memory_used_mib} MiB`}</td>
                            <td>{device.temperature_celsius === undefined ? "—" : `${device.temperature_celsius}°C`}</td>
                            <td>{device.power_watts === undefined ? "—" : `${device.power_watts} W`}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">No hardware readings available.</p>
                )}
              </div>
            </section>
          )}
          <section className="mt-10 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-xl font-semibold">Users</h2>
            <form onSubmit={searchUsers} className="mt-4 flex gap-3">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search email or name"
                className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
              />
              <button className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white">
                Search
              </button>
            </form>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2">Account</th>
                    <th>Access</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td className="py-3">
                        <p className="font-medium">
                          {user.display_name || user.email}
                        </p>
                        <p className="text-xs text-slate-500">
                          {user.email} ·{" "}
                          {user.email_verified ? "verified" : "unverified"}
                        </p>
                      </td>
                      <td>
                        {user.level}
                        {user.is_banned ? " · banned" : ""}
                        {user.staff_role !== "user"
                          ? ` · ${user.staff_role}`
                          : ""}
                      </td>
                      <td>{new Date(user.created_at).toLocaleDateString()}</td>
                      <td>
                        <div className="flex gap-3">
                          <button
                            type="button"
                            onClick={() => void toggleBan(user)}
                            className="font-semibold text-violet-700"
                          >
                            {user.is_banned ? "Unban" : "Ban"}
                          </button>
                          <button
                            type="button"
                            onClick={() => void grantCredits(user)}
                            className="font-semibold text-violet-700"
                          >
                            Grant 10 credits
                          </button>
                          {overview.actor_role === "super_admin" &&
                            user.staff_role !== "super_admin" && (
                              <button
                                type="button"
                                onClick={() => void toggleRole(user)}
                                className="font-semibold text-violet-700"
                              >
                                {user.staff_role === "admin"
                                  ? "Remove admin"
                                  : "Make admin"}
                              </button>
                            )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="mt-8 grid gap-8 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <h2 className="text-xl font-semibold">Tool controls</h2>
              <ul className="mt-3 divide-y divide-slate-200 dark:divide-slate-700">
                {tools.map((tool) => (
                  <li
                    key={tool.slug}
                    className="flex flex-wrap items-center justify-between gap-3 py-3"
                  >
                    <span>
                      <strong>{tool.name}</strong>
                      <span className="ml-2 text-xs text-slate-500">
                        {tool.slug}
                      </span>
                    </span>
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => void toggleTool(tool)}
                        className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold dark:border-slate-600"
                      >
                        {tool.enabled ? "Enabled" : "Disabled"}
                      </button>
                      {tool.job_tier && (
                        <details className="relative">
                          <summary className="cursor-pointer text-xs font-semibold text-violet-700">
                            {tool.prices[`job_${tool.job_tier.toLowerCase()}`] ?? tool.single_job_price_cents ?? 0}¢
                          </summary>
                          <form
                            onSubmit={(event) => void saveToolPrice(event, tool)}
                            className="absolute right-0 z-10 mt-2 flex w-52 gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow-lg dark:border-slate-700 dark:bg-slate-900"
                          >
                            <input
                              name="price_cents"
                              type="number"
                              min="1"
                              step="1"
                              defaultValue={String(tool.prices[`job_${tool.job_tier.toLowerCase()}`] ?? tool.single_job_price_cents ?? "")}
                              aria-label={`Single job price in cents for ${tool.name}`}
                              className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-transparent px-2 py-1.5 text-sm dark:border-slate-600"
                            />
                            <button className="rounded-lg bg-violet-600 px-2 py-1.5 text-xs font-semibold text-white">Save</button>
                          </form>
                        </details>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <h2 className="text-xl font-semibold">Recent jobs</h2>
              <ul className="mt-3 divide-y divide-slate-200 dark:divide-slate-700">
                {jobs.slice(0, 25).map((job) => (
                  <li
                    key={job.job_id}
                    className="flex items-center justify-between gap-3 py-3 text-sm"
                  >
                    <span>
                      {job.tool_slug} · {job.state}
                    </span>
                    <span className="text-xs text-slate-500">
                      {job.progress}% ·{" "}
                      {job.error_code || job.job_id.slice(0, 8)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
          <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-xl font-semibold">Abuse reports</h2>
            {reports.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No QR abuse reports have been submitted.</p>
            ) : (
              <ul className="mt-3 divide-y divide-slate-200 dark:divide-slate-700">
                {reports.map((report) => (
                  <li key={report.id} className="flex flex-wrap items-start justify-between gap-4 py-4">
                    <div className="min-w-0">
                      <p className="font-medium">
                        QR {report.code} · {report.status}
                      </p>
                      <p className="mt-1 break-all text-sm text-slate-500">{report.target_url}</p>
                      {report.message && <p className="mt-2 text-sm">{report.message}</p>}
                      <p className="mt-1 text-xs text-slate-500">
                        Reported {new Date(report.created_at).toLocaleString()}
                        {report.resolved_at && ` · Resolved ${new Date(report.resolved_at).toLocaleString()}`}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {report.qr_id && (
                        <button
                          type="button"
                          onClick={() => void disableReportedCode(report)}
                          className="rounded-lg border border-red-300 px-3 py-1.5 text-sm text-red-700 dark:border-red-800 dark:text-red-300"
                        >
                          Disable QR code
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => void setReportResolved(report, report.status !== "resolved")}
                        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600"
                      >
                        {report.status === "resolved" ? "Reopen" : "Mark resolved"}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-xl font-semibold">Audit log</h2>
            <ul className="mt-3 divide-y divide-slate-200 dark:divide-slate-700">
              {audit.slice(0, 30).map((row) => (
                <li key={row.id} className="py-3 text-sm">
                  <span className="font-medium">{row.action}</span>
                  <span className="ml-2 text-slate-500">
                    {row.target || ""} ·{" "}
                    {new Date(row.created_at).toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </main>
  );
}
