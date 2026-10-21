"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type MonitorCheck = {
  checked_at: string;
  status_code: number | null;
  response_ms: number;
  error_code: string | null;
};

type Monitor = {
  id: string;
  name: string;
  url: string;
  active: boolean;
  interval_seconds: number;
  last_checked_at: string | null;
  last_status_code: number | null;
  last_response_ms: number | null;
  last_error_code: string | null;
  consecutive_failures: number;
  has_webhook: boolean;
  has_sms: boolean;
  checks: MonitorCheck[];
};

async function request(path: string, method = "GET", body?: object) {
  const headers: Record<string, string> = {};
  if (body) {
    const csrfResponse = await fetch("/api/auth/csrf", {
      credentials: "include",
    });
    if (!csrfResponse.ok) throw new Error("Could not start a secure request.");
    const { csrf_token: csrf } = (await csrfResponse.json()) as {
      csrf_token: string;
    };
    headers["Content-Type"] = "application/json";
    headers["X-RC-CSRF"] = csrf;
  }
  const response = await fetch(path, {
    method,
    credentials: "include",
    cache: "no-store",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok && response.status !== 204) {
    const result = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(result.detail || "The monitor request failed.");
  }
  return response.status === 204 || response.status === 202
    ? null
    : response.json();
}

export function MonitorManager() {
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const result = (await request("/api/monitors")) as Monitor[];
    setMonitors(result);
  }, []);

  useEffect(() => {
    void load().catch((cause: unknown) =>
      setError(cause instanceof Error ? cause.message : "Could not load monitors."),
    );
  }, [load]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    setError("");
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      await request("/api/monitors", "POST", {
        name: String(form.get("name") || ""),
        url: String(form.get("url") || ""),
        webhook_url: String(form.get("webhook_url") || "") || null,
        sms_phone: String(form.get("sms_phone") || "") || null,
        sms_consent: form.get("sms_consent") === "on",
      });
      formElement.reset();
      setMessage("Monitor created. Its first check is queued.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create monitor.");
    } finally {
      setBusy(false);
    }
  }

  async function setActive(monitor: Monitor, active: boolean) {
    try {
      await request(`/api/monitors/${monitor.id}`, "PATCH", { active });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update monitor.");
    }
  }

  async function disableSms(monitor: Monitor) {
    try {
      await request(`/api/monitors/${monitor.id}`, "PATCH", { sms_consent: false });
      setMessage("SMS alerts disabled for this monitor.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not disable SMS alerts.");
    }
  }

  async function checkNow(monitor: Monitor) {
    try {
      await request(`/api/monitors/${monitor.id}/check`, "POST", {});
      setMessage(`A check for ${monitor.name} was queued.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not queue a check.");
    }
  }

  async function remove(monitor: Monitor) {
    try {
      await request(`/api/monitors/${monitor.id}`, "DELETE", {});
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete monitor.");
    }
  }

  return (
    <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Uptime monitors</h2>
          <p className="mt-1 text-sm text-slate-500">
            Free accounts check one site every 15 minutes. Pro and day-pass access checks every minute.
          </p>
        </div>
      </div>
      {(error || message) && (
        <p
          role={error ? "alert" : "status"}
          className={`mt-4 rounded-xl p-3 text-sm ${error ? "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200" : "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"}`}
        >
          {error || message}
        </p>
      )}
      <form onSubmit={(event) => void create(event)} className="mt-5 grid gap-3 md:grid-cols-3">
        <input
          name="name"
          required
          maxLength={80}
          placeholder="Monitor name"
          aria-label="Monitor name"
          className="rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
        />
        <input
          name="url"
          required
          type="url"
          maxLength={2048}
          placeholder="https://example.com/health"
          aria-label="Website URL to monitor"
          className="rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
        />
        <input
          name="webhook_url"
          type="url"
          maxLength={2048}
          placeholder="Optional Pro Discord or Slack webhook"
          aria-label="Optional Discord or Slack webhook URL"
          className="rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
        />
        <input
          name="sms_phone"
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          placeholder="Optional Pro SMS phone, e.g. +15551234567"
          aria-label="Optional SMS phone number in international format"
          pattern="\\+[1-9][0-9]{7,14}"
          maxLength={16}
          className="rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
        />
        <label className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300 md:col-span-3">
          <input name="sms_consent" type="checkbox" className="mt-1" />
          <span>
            I agree to receive uptime and recovery alerts by SMS. Each accepted SMS uses 1 credit,
            up to the monthly account cap. Message and carrier fees may apply.
          </span>
        </label>
        <button
          disabled={busy}
          className="rounded-xl bg-violet-600 px-4 py-2 font-semibold text-white disabled:opacity-50 md:col-span-3 md:justify-self-start"
        >
          {busy ? "Creating…" : "Add monitor"}
        </button>
      </form>
      <ul className="mt-6 divide-y divide-slate-200 dark:divide-slate-700">
        {monitors.map((monitor) => (
          <li key={monitor.id} className="py-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <h3 className="font-semibold">{monitor.name}</h3>
                <p className="mt-1 break-all text-sm text-slate-500">{monitor.url}</p>
                <p className="mt-2 text-sm">
                  {monitor.last_error_code
                    ? `Down · ${monitor.last_error_code}`
                    : monitor.last_status_code
                      ? `Up · HTTP ${monitor.last_status_code}`
                      : "Waiting for first check"}
                  {monitor.last_response_ms !== null && ` · ${monitor.last_response_ms} ms`}
                  {` · checks every ${Math.round(monitor.interval_seconds / 60)} min`}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {monitor.last_checked_at
                    ? `Last checked ${new Date(monitor.last_checked_at).toLocaleString()}`
                    : "No check has completed yet"}
                  {monitor.has_webhook ? " · Discord/Slack alerts enabled" : " · email alerts enabled"}
                  {monitor.has_sms && " · SMS alerts enabled"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-sm">
                <button onClick={() => void checkNow(monitor)} className="rounded-lg border border-slate-300 px-3 py-1.5 dark:border-slate-600">
                  Check now
                </button>
                <button onClick={() => void setActive(monitor, !monitor.active)} className="rounded-lg border border-slate-300 px-3 py-1.5 dark:border-slate-600">
                  {monitor.active ? "Pause" : "Resume"}
                </button>
                {monitor.has_sms && (
                  <button onClick={() => void disableSms(monitor)} className="rounded-lg border border-slate-300 px-3 py-1.5 dark:border-slate-600">
                    Disable SMS
                  </button>
                )}
                <button onClick={() => void remove(monitor)} className="rounded-lg border border-red-300 px-3 py-1.5 text-red-700 dark:border-red-800 dark:text-red-300">
                  Delete
                </button>
              </div>
            </div>
            {monitor.checks.length > 0 && (
              <details className="mt-3 text-sm">
                <summary className="cursor-pointer font-medium">Recent checks ({monitor.checks.length})</summary>
                <ul className="mt-2 grid gap-1 text-xs text-slate-500 sm:grid-cols-2">
                  {monitor.checks.slice(0, 10).map((check) => (
                    <li key={check.checked_at}>
                      {new Date(check.checked_at).toLocaleString()} · {check.error_code || `HTTP ${check.status_code}`} · {check.response_ms} ms
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
