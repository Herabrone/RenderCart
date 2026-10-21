"use client";

import { useCallback, useEffect, useState } from "react";

type Audit = {
  id: string;
  job_id: string | null;
  url: string;
  scores: Record<string, number | null>;
  findings: { title: string; display_value: string; score: number }[];
  created_at: string;
};

type Schedule = {
  id: string;
  url: string;
  device: "mobile" | "desktop";
  active: boolean;
  next_run_at: string;
  last_error_code: string | null;
};

const scoreLabels: Record<string, string> = {
  performance: "Performance",
  accessibility: "Accessibility",
  "best-practices": "Best practices",
  seo: "SEO",
};

export function WebsiteAuditHistory() {
  const [audits, setAudits] = useState<Audit[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [scheduleUrl, setScheduleUrl] = useState("");
  const [scheduleDevice, setScheduleDevice] = useState<"mobile" | "desktop">(
    "mobile",
  );
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/website-audits", {
        credentials: "include",
        cache: "no-store",
      });
      if (response.status === 401) {
        setMessage(
          "Sign in with a Pro account to keep and view audit history.",
        );
        setAudits([]);
      } else if (response.status === 402) {
        setMessage(
          "Pro includes saved audit history. Your current report is still available above.",
        );
        setAudits([]);
      } else if (!response.ok) {
        throw new Error("Could not load audit history.");
      } else {
        setAudits((await response.json()) as Audit[]);
        setMessage("");
        const scheduleResponse = await fetch("/api/website-audits/schedules", {
          credentials: "include",
          cache: "no-store",
        });
        if (!scheduleResponse.ok)
          throw new Error("Could not load weekly audit schedules.");
        setSchedules((await scheduleResponse.json()) as Schedule[]);
      }
    } catch (cause) {
      setMessage(
        cause instanceof Error
          ? cause.message
          : "Could not load audit history.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  async function csrfToken() {
    const response = await fetch("/api/auth/csrf", { credentials: "include" });
    if (!response.ok) throw new Error("Could not start a secure request.");
    return ((await response.json()) as { csrf_token: string }).csrf_token;
  }

  async function createSchedule(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingSchedule(true);
    try {
      const token = await csrfToken();
      const response = await fetch("/api/website-audits/schedules", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
        body: JSON.stringify({ url: scheduleUrl, device: scheduleDevice }),
      });
      if (!response.ok) {
        const result = (await response.json()) as { detail?: string };
        throw new Error(result.detail ?? "Could not create weekly audit.");
      }
      setScheduleUrl("");
      setMessage("");
      await load();
    } catch (cause) {
      setMessage(
        cause instanceof Error
          ? cause.message
          : "Could not create weekly audit.",
      );
    } finally {
      setSavingSchedule(false);
    }
  }

  async function deleteSchedule(id: string) {
    try {
      const token = await csrfToken();
      const response = await fetch(`/api/website-audits/schedules/${id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-RC-CSRF": token },
      });
      if (!response.ok) throw new Error("Could not remove weekly audit.");
      setSchedules((current) => current.filter((item) => item.id !== id));
    } catch (cause) {
      setMessage(
        cause instanceof Error
          ? cause.message
          : "Could not remove weekly audit.",
      );
    }
  }

  useEffect(() => {
    void load();
  }, [load]);

  async function download(jobId: string) {
    try {
      const response = await fetch(`/api/jobs/${jobId}`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!response.ok)
        throw new Error(
          "This PDF has expired. Run the audit again to export a fresh report.",
        );
      const result = (await response.json()) as { download_url?: string };
      if (!result.download_url)
        throw new Error("The PDF is no longer available.");
      window.location.assign(result.download_url);
    } catch (cause) {
      setMessage(
        cause instanceof Error
          ? cause.message
          : "Could not download this report.",
      );
    }
  }

  return (
    <section className="mt-8 rounded-3xl border border-line bg-surface p-6  ">
      <div className="mb-8 border-b border-line pb-6 ">
        <h2 className="text-xl font-semibold">Weekly scheduled audits</h2>
        <p className="mt-1 text-sm text-muted">
          Pro accounts can schedule up to five public HTTPS pages. Each run uses
          2 credits.
        </p>
        <form
          onSubmit={(event) => void createSchedule(event)}
          className="mt-4 flex flex-wrap gap-3"
        >
          <label className="sr-only" htmlFor="weekly-audit-url">
            Website URL
          </label>
          <input
            id="weekly-audit-url"
            type="url"
            required
            value={scheduleUrl}
            onChange={(event) => setScheduleUrl(event.target.value)}
            placeholder="https://example.com"
            className="min-w-64 flex-1 rounded-lg border border-line-strong bg-transparent px-3 py-2 text-sm "
          />
          <label className="sr-only" htmlFor="weekly-audit-device">
            Device profile
          </label>
          <select
            id="weekly-audit-device"
            value={scheduleDevice}
            onChange={(event) =>
              setScheduleDevice(event.target.value as "mobile" | "desktop")
            }
            className="rounded-lg border border-line-strong bg-transparent px-3 py-2 text-sm "
          >
            <option value="mobile">Mobile</option>
            <option value="desktop">Desktop</option>
          </select>
          <button
            disabled={savingSchedule || schedules.length >= 5}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {savingSchedule ? "Saving…" : "Schedule weekly"}
          </button>
        </form>
        {schedules.length > 0 && (
          <ul className="mt-4 divide-y divide-line ">
            {schedules.map((schedule) => (
              <li
                key={schedule.id}
                className="flex flex-wrap items-center justify-between gap-3 py-3"
              >
                <div className="min-w-0">
                  <p className="break-all text-sm font-medium">
                    {schedule.url}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {schedule.device} · next run{" "}
                    {new Date(schedule.next_run_at).toLocaleString()}
                    {schedule.last_error_code
                      ? ` · ${schedule.last_error_code.replaceAll("_", " ")}`
                      : ""}
                  </p>
                </div>
                <button
                  onClick={() => void deleteSchedule(schedule.id)}
                  className="rounded-lg border border-line-strong px-3 py-1.5 text-sm "
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Audit history</h2>
          <p className="mt-1 text-sm text-muted">
            Pro accounts keep the 50 most recent audit summaries.
          </p>
        </div>
        <button
          onClick={() => void load()}
          disabled={loading}
          className="rounded-lg border border-line-strong px-3 py-2 text-sm "
        >
          {loading ? "Loading…" : "Refresh history"}
        </button>
      </div>
      {message && (
        <p role="status" className="mt-4 text-sm text-muted ">
          {message}
        </p>
      )}
      {!message && audits.length === 0 && !loading && (
        <p className="mt-4 text-sm text-muted">
          Completed audits will appear here.
        </p>
      )}
      <ul className="mt-4 divide-y divide-line ">
        {audits.map((audit) => (
          <li key={audit.id} className="py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="break-all text-sm font-semibold">{audit.url}</p>
                <p className="mt-1 text-xs text-muted">
                  {new Date(audit.created_at).toLocaleString()}
                </p>
              </div>
              {audit.job_id && (
                <button
                  onClick={() => void download(audit.job_id!)}
                  className="rounded-lg border border-line-strong px-3 py-1.5 text-sm "
                >
                  Download PDF
                </button>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(scoreLabels).map(([key, label]) => (
                <span
                  key={key}
                  className="rounded-lg bg-subtle px-2.5 py-1 text-xs "
                >
                  {label}: {audit.scores[key] ?? "N/A"}
                  {audit.scores[key] === null ? "" : "/100"}
                </span>
              ))}
            </div>
            {audit.findings.length > 0 && (
              <ul className="mt-3 space-y-1 text-xs text-muted ">
                {audit.findings.slice(0, 3).map((finding, index) => (
                  <li key={`${finding.title}-${index}`}>
                    {finding.title}
                    {finding.display_value ? ` · ${finding.display_value}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
