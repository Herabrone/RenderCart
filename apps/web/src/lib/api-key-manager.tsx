"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type ApiKeyInfo = {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

async function secureRequest(
  url: string,
  method: "POST" | "DELETE",
  body?: object,
) {
  const csrfResponse = await fetch("/api/auth/csrf", {
    credentials: "include",
  });
  if (!csrfResponse.ok) throw new Error("Could not start a secure request.");
  const { csrf_token: token } = (await csrfResponse.json()) as {
    csrf_token: string;
  };
  const response = await fetch(url, {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(detail.detail || "API key request failed.");
  }
  return response.status === 204 ? null : response.json();
}

export function ApiKeyManager() {
  const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
  const [name, setName] = useState("");
  const [newKey, setNewKey] = useState("");
  const [message, setMessage] = useState("");

  const loadKeys = useCallback(async () => {
    const response = await fetch("/api/account/api-keys", {
      credentials: "include",
      cache: "no-store",
    });
    if (response.status === 402) {
      setMessage("Developer API keys are available with Pro.");
      return;
    }
    if (!response.ok) throw new Error("Could not load API keys.");
    setKeys((await response.json()) as ApiKeyInfo[]);
  }, []);

  useEffect(() => {
    void loadKeys().catch((error: unknown) =>
      setMessage(
        error instanceof Error ? error.message : "Could not load API keys.",
      ),
    );
  }, [loadKeys]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setNewKey("");
    try {
      const result = (await secureRequest("/api/account/api-keys", "POST", {
        name,
      })) as { key: string };
      setNewKey(result.key);
      setName("");
      await loadKeys();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Could not create API key.",
      );
    }
  }

  async function revoke(id: string) {
    setMessage("");
    try {
      await secureRequest(`/api/account/api-keys/${id}`, "DELETE");
      await loadKeys();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Could not revoke API key.",
      );
    }
  }

  return (
    <section className="mt-8 border-t border-slate-200 pt-6 dark:border-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Developer API keys</h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Pro accounts can use the public tools API. Keys are shown only once.
          </p>
        </div>
        <a
          className="text-sm font-semibold text-violet-700 dark:text-violet-300"
          href="/developers"
        >
          API documentation
        </a>
      </div>
      <form onSubmit={create} className="mt-4 flex flex-wrap gap-3">
        <input
          required
          minLength={1}
          maxLength={80}
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Key name, e.g. Production server"
          className="min-w-56 flex-1 rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
        />
        <button className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white">
          Create key
        </button>
      </form>
      {newKey && (
        <div className="mt-4 rounded-xl border border-amber-400 bg-amber-50 p-4 dark:bg-amber-950">
          <p className="text-sm font-semibold">
            Copy this key now. It will not be shown again.
          </p>
          <code className="mt-2 block break-all text-sm">{newKey}</code>
          <button
            type="button"
            className="mt-3 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold dark:border-slate-600"
            onClick={() => void navigator.clipboard.writeText(newKey)}
          >
            Copy key
          </button>
        </div>
      )}
      {keys.length > 0 && (
        <ul className="mt-4 divide-y divide-slate-200 dark:divide-slate-700">
          {keys.map((key) => (
            <li
              key={key.id}
              className="flex flex-wrap items-center justify-between gap-3 py-3"
            >
              <div>
                <p className="text-sm font-semibold">
                  {key.name} · {key.prefix}…
                </p>
                <p className="text-xs text-slate-500">
                  {key.revoked_at ? "Revoked" : "Active"} · Created{" "}
                  {new Date(key.created_at).toLocaleDateString()}
                  {key.last_used_at
                    ? ` · Last used ${new Date(key.last_used_at).toLocaleString()}`
                    : " · Not used yet"}
                </p>
              </div>
              {!key.revoked_at && (
                <button
                  type="button"
                  onClick={() => void revoke(key.id)}
                  className="text-sm font-semibold text-red-700"
                >
                  Revoke
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {message && (
        <p
          role="status"
          className="mt-3 text-sm text-slate-600 dark:text-slate-300"
        >
          {message}
        </p>
      )}
    </section>
  );
}
