"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type WebhookBin = {
  id: string;
  name: string;
  token_prefix: string;
  expires_at: string;
  created_at: string;
  event_count: number;
};
type WebhookEvent = {
  id: string;
  method: string;
  received_at: string;
  payload: Record<string, unknown>;
};

async function binRequest(path: string, method = "GET", body?: object) {
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
    throw new Error(result.detail || "The webhook bin request failed.");
  }
  return response.status === 204 ? null : response.json();
}

export function WebhookBinManager() {
  const [bins, setBins] = useState<WebhookBin[]>([]);
  const [events, setEvents] = useState<Record<string, WebhookEvent[]>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [createdEndpoint, setCreatedEndpoint] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBins((await binRequest("/api/webhook-bins")) as WebhookBin[]);
  }, []);

  useEffect(() => {
    void load().catch((cause: unknown) =>
      setError(
        cause instanceof Error ? cause.message : "Could not load webhook bins.",
      ),
    );
  }, [load]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const name = String(new FormData(form).get("name") || "");
    setBusy(true);
    setError("");
    setMessage("");
    setCreatedEndpoint("");
    try {
      const result = (await binRequest("/api/webhook-bins", "POST", {
        name,
      })) as WebhookBin & {
        endpoint_url: string;
      };
      setCreatedEndpoint(result.endpoint_url);
      setMessage("Copy the endpoint now. Its token is shown only once.");
      form.reset();
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not create webhook bin.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function showEvents(bin: WebhookBin) {
    setSelected(bin.id);
    setError("");
    try {
      const result = (await binRequest(
        `/api/webhook-bins/${bin.id}/events`,
      )) as WebhookEvent[];
      setEvents((current) => ({ ...current, [bin.id]: result }));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not load captured requests.",
      );
    }
  }

  async function remove(bin: WebhookBin) {
    try {
      await binRequest(`/api/webhook-bins/${bin.id}`, "DELETE", {});
      if (selected === bin.id) setSelected(null);
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not delete webhook bin.",
      );
    }
  }

  return (
    <section className="mt-8 rounded-3xl border border-line bg-surface p-6  ">
      <h2 className="text-xl font-semibold">Webhook tester</h2>
      <p className="mt-1 text-sm text-muted">
        Free bins expire after one hour; Pro and day-pass bins expire after
        seven days. Captured bodies are encrypted and limited to 64 KB.
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
          name="name"
          required
          maxLength={80}
          placeholder="Checkout test"
          aria-label="Webhook bin name"
          className="min-w-0 flex-1 rounded-xl border border-line-strong bg-transparent px-3 py-2 "
        />
        <button
          disabled={busy}
          className="rounded-xl bg-accent px-4 py-2 font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Creating…" : "Create bin"}
        </button>
      </form>
      {createdEndpoint && (
        <div className="mt-4 rounded-xl bg-canvas p-4 ">
          <p className="text-sm font-semibold">Webhook endpoint (copy now)</p>
          <code className="mt-2 block break-all text-xs">
            {createdEndpoint}
          </code>
          <button
            type="button"
            onClick={() => void navigator.clipboard.writeText(createdEndpoint)}
            className="mt-3 text-sm font-semibold text-accent "
          >
            Copy endpoint
          </button>
        </div>
      )}
      <ul className="mt-5 divide-y divide-line ">
        {bins.map((bin) => (
          <li key={bin.id} className="py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold">{bin.name}</h3>
                <p className="mt-1 text-xs text-muted">
                  Token {bin.token_prefix}… · {bin.event_count} request(s) ·
                  expires {new Date(bin.expires_at).toLocaleString()}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void showEvents(bin)}
                  className="rounded-lg border border-line-strong px-3 py-1.5 text-sm "
                >
                  View requests
                </button>
                <button
                  type="button"
                  onClick={() => void remove(bin)}
                  className="rounded-lg border border-red-300 px-3 py-1.5 text-sm text-red-700  "
                >
                  Delete
                </button>
              </div>
            </div>
            {selected === bin.id && (
              <ul className="mt-3 space-y-3">
                {(events[bin.id] ?? []).length === 0 ? (
                  <li className="text-sm text-muted">
                    No requests received yet.
                  </li>
                ) : (
                  (events[bin.id] ?? []).map((item) => (
                    <li key={item.id} className="rounded-xl bg-canvas p-3 ">
                      <p className="text-xs font-semibold">
                        {item.method} ·{" "}
                        {new Date(item.received_at).toLocaleString()}
                      </p>
                      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all text-xs">
                        {JSON.stringify(item.payload, null, 2)}
                      </pre>
                    </li>
                  ))
                )}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
