"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type DomainAlert = {
  id: string;
  domain: string;
  active: boolean;
  last_checked_at: string | null;
  tls_expires_at: string | null;
  domain_expires_at: string | null;
  tls_error_code: string | null;
  domain_error_code: string | null;
};

async function domainAlertRequest(path: string, method = "GET", body?: object) {
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
    throw new Error(result.detail || "The domain alert request failed.");
  }
  return response.status === 204 ? null : response.json();
}

function dateValue(value: string | null): string {
  return value ? new Date(value).toLocaleDateString() : "Not available yet";
}

export function DomainAlertManager() {
  const [alerts, setAlerts] = useState<DomainAlert[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setAlerts(
      (await domainAlertRequest("/api/domain-alerts")) as DomainAlert[],
    );
  }, []);

  useEffect(() => {
    void load().catch((cause: unknown) =>
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not load domain alerts.",
      ),
    );
  }, [load]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const domain = String(new FormData(form).get("domain") || "");
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await domainAlertRequest("/api/domain-alerts", "POST", { domain });
      form.reset();
      setMessage(
        "Domain alert created. Certificate and RDAP checks are queued.",
      );
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not create domain alert.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function setActive(alert: DomainAlert, active: boolean) {
    try {
      await domainAlertRequest(`/api/domain-alerts/${alert.id}`, "PATCH", {
        active,
      });
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not update domain alert.",
      );
    }
  }

  async function remove(alert: DomainAlert) {
    try {
      await domainAlertRequest(`/api/domain-alerts/${alert.id}`, "DELETE", {});
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not delete domain alert.",
      );
    }
  }

  return (
    <section className="mt-8 rounded-3xl border border-line bg-surface p-6  ">
      <h2 className="text-xl font-semibold">SSL and domain expiry alerts</h2>
      <p className="mt-1 text-sm text-muted">
        Certificate and RDAP registration dates are checked daily. Email alerts
        arrive within 30 days of expiry.
      </p>
      {(error || message) && (
        <p
          role={error ? "alert" : "status"}
          className={`mt-4 rounded-xl p-3 text-sm ${error ? "bg-red-50 text-red-800  " : "bg-emerald-50 text-emerald-800  "}`}
        >
          {error || message}
        </p>
      )}
      <form
        onSubmit={(event) => void create(event)}
        className="mt-5 flex flex-wrap gap-3"
      >
        <input
          name="domain"
          required
          maxLength={253}
          placeholder="example.com"
          aria-label="Domain name"
          className="min-w-0 flex-1 rounded-xl border border-line-strong bg-transparent px-3 py-2 "
        />
        <button
          disabled={busy}
          className="rounded-xl bg-accent px-4 py-2 font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Creating…" : "Add domain"}
        </button>
      </form>
      <ul className="mt-5 divide-y divide-line ">
        {alerts.map((alert) => (
          <li
            key={alert.id}
            className="flex flex-wrap items-start justify-between gap-4 py-4"
          >
            <div>
              <h3 className="font-semibold">
                {alert.domain}
                {!alert.active && " · paused"}
              </h3>
              <p className="mt-1 text-sm text-muted ">
                TLS certificate expires: {dateValue(alert.tls_expires_at)}
                {alert.tls_error_code && ` · ${alert.tls_error_code}`}
              </p>
              <p className="mt-1 text-sm text-muted ">
                Domain registration expires:{" "}
                {dateValue(alert.domain_expires_at)}
                {alert.domain_error_code && ` · ${alert.domain_error_code}`}
              </p>
              <p className="mt-1 text-xs text-muted">
                {alert.last_checked_at
                  ? `Last checked ${new Date(alert.last_checked_at).toLocaleString()}`
                  : "Waiting for first check"}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void setActive(alert, !alert.active)}
                className="rounded-lg border border-line-strong px-3 py-1.5 text-sm "
              >
                {alert.active ? "Pause" : "Resume"}
              </button>
              <button
                type="button"
                onClick={() => void remove(alert)}
                className="rounded-lg border border-red-300 px-3 py-1.5 text-sm text-red-700  "
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
