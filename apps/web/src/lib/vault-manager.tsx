"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type VaultItem = {
  id: string;
  url: string;
  created_at: string;
  expires_at: string;
  filename?: string;
  size_bytes?: number;
};

async function secureRequest(path: string, method: "POST" | "DELETE", body?: object) {
  const csrfResponse = await fetch("/api/auth/csrf", { credentials: "include" });
  if (!csrfResponse.ok) throw new Error("Could not start a secure request.");
  const { csrf_token: csrf } = (await csrfResponse.json()) as { csrf_token: string };
  const response = await fetch(path, {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-RC-CSRF": csrf },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(payload.detail ?? "The Vault request failed.");
  }
  return response.status === 204 ? null : response.json();
}

function formatExpiry(value: string) {
  return new Date(value).toLocaleString();
}

export default function VaultManager() {
  const [links, setLinks] = useState<VaultItem[]>([]);
  const [pastes, setPastes] = useState<VaultItem[]>([]);
  const [files, setFiles] = useState<VaultItem[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [target, setTarget] = useState("");
  const [content, setContent] = useState("");
  const [ttl, setTtl] = useState(604800);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    const response = await fetch("/api/vault", { credentials: "include", cache: "no-store" });
    if (!response.ok) throw new Error("Vault is unavailable.");
    const data = (await response.json()) as {
      short_links: VaultItem[];
      pastes: VaultItem[];
      files: VaultItem[];
    };
    setLinks(data.short_links);
    setPastes(data.pastes);
    setFiles(data.files);
  }, []);

  useEffect(() => {
    void refresh().catch((cause: unknown) =>
      setError(cause instanceof Error ? cause.message : "Vault is unavailable."),
    );
  }, [refresh]);

  async function createLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = (await secureRequest("/api/vault/short-links", "POST", {
        target_url: target,
        ttl_seconds: ttl,
      })) as VaultItem;
      setTarget("");
      await refresh();
      await navigator.clipboard.writeText(created.url);
      setNotice("Short link created and copied to your clipboard.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the short link.");
    } finally {
      setBusy(false);
    }
  }

  async function createPaste(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = (await secureRequest("/api/vault/pastes", "POST", {
        content,
        ttl_seconds: ttl,
      })) as VaultItem;
      setContent("");
      await refresh();
      await navigator.clipboard.writeText(created.url);
      setNotice("Text share created and copied to your clipboard.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the text share.");
    } finally {
      setBusy(false);
    }
  }

  async function createFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const csrfResponse = await fetch("/api/auth/csrf", { credentials: "include" });
      if (!csrfResponse.ok) throw new Error("Could not start a secure request.");
      const { csrf_token: csrf } = (await csrfResponse.json()) as { csrf_token: string };
      const response = await fetch("/api/vault/files", {
        method: "PUT",
        credentials: "include",
        headers: {
          "X-RC-CSRF": csrf,
          "X-RC-File-Name": encodeURIComponent(file.name),
          "X-RC-TTL-Seconds": String(ttl),
          "Content-Type": "application/octet-stream",
        },
        body: file,
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(payload.detail ?? "Could not create the file share.");
      }
      const created = (await response.json()) as VaultItem;
      setFile(null);
      await refresh();
      await navigator.clipboard.writeText(created.url);
      setNotice("Encrypted file share created and copied to your clipboard.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the file share.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(kind: "short-links" | "pastes" | "files", item: VaultItem) {
    setError("");
    setNotice("");
    try {
      await secureRequest(`/api/vault/${kind}/${item.id}`, "DELETE");
      await refresh();
      setNotice("Item deleted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete this item.");
    }
  }

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice("Copied to your clipboard.");
    } catch {
      setError("Clipboard access was denied by the browser.");
    }
  }

  return (
    <section className="mt-8 space-y-8">
      {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {notice && <p role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}

      <label className="block max-w-xs text-sm font-semibold">
        Expiration
        <select value={ttl} onChange={(event) => setTtl(Number(event.target.value))} className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600">
          <option value={3600}>1 hour</option>
          <option value={86400}>1 day</option>
          <option value={604800}>7 days</option>
          <option value={2592000}>30 days</option>
        </select>
      </label>

      <div className="grid gap-6 md:grid-cols-2">
        <form onSubmit={(event) => void createLink(event)} className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700">
          <h2 className="text-lg font-semibold">Temporary short link</h2>
          <label className="mt-4 block text-sm font-medium">Destination URL
            <input type="url" required maxLength={2048} value={target} onChange={(event) => setTarget(event.target.value)} placeholder="https://example.com/page" className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600" />
          </label>
          <button disabled={busy} className="mt-4 rounded-xl bg-violet-600 px-4 py-2 font-semibold text-white disabled:opacity-50">Create short link</button>
        </form>

        <form onSubmit={(event) => void createPaste(event)} className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700">
          <h2 className="text-lg font-semibold">Temporary text share</h2>
          <label className="mt-4 block text-sm font-medium">Text (up to 20,000 characters)
            <textarea required maxLength={20_000} value={content} onChange={(event) => setContent(event.target.value)} className="mt-2 block min-h-32 w-full rounded-xl border border-slate-300 bg-transparent p-3 font-normal dark:border-slate-600" />
          </label>
          <button disabled={busy} className="mt-4 rounded-xl bg-violet-600 px-4 py-2 font-semibold text-white disabled:opacity-50">Create text share</button>
        </form>
      </div>

      <form onSubmit={(event) => void createFile(event)} className="max-w-2xl rounded-2xl border border-slate-200 p-5 dark:border-slate-700">
        <h2 className="text-lg font-semibold">Temporary file share</h2>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Files up to 25 MB are encrypted before they are stored.</p>
        <label className="mt-4 block text-sm font-medium">Choose a file
          <input type="file" required onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-2 block w-full text-sm" />
        </label>
        <button disabled={busy || !file || file.size > 25 * 1024 * 1024} className="mt-4 rounded-xl bg-violet-600 px-4 py-2 font-semibold text-white disabled:opacity-50">Create encrypted file share</button>
      </form>

      <ItemList title="Short links" items={links} onCopy={copy} onDelete={(item) => remove("short-links", item)} />
      <ItemList title="Text shares" items={pastes} onCopy={copy} onDelete={(item) => remove("pastes", item)} />
      <ItemList title="File shares" items={files} onCopy={copy} onDelete={(item) => remove("files", item)} />
    </section>
  );
}

function ItemList({
  title,
  items,
  onCopy,
  onDelete,
}: {
  title: string;
  items: VaultItem[];
  onCopy: (url: string) => void;
  onDelete: (item: VaultItem) => void;
}) {
  return (
    <section>
      <h2 className="text-lg font-semibold">{title}</h2>
      {items.length === 0 ? <p className="mt-2 text-sm text-slate-500">No active items.</p> : (
        <ul className="mt-3 divide-y divide-slate-200 rounded-xl border border-slate-200 dark:divide-slate-700 dark:border-slate-700">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <a href={item.url} target="_blank" rel="noreferrer" className="break-all font-medium text-violet-700 underline dark:text-violet-300">{item.url}</a>
                {item.filename && <p className="mt-1 break-all text-sm">{item.filename} · {Math.ceil((item.size_bytes ?? 0) / 1024)} KB</p>}
                <p className="mt-1 text-xs text-slate-500">Expires {formatExpiry(item.expires_at)}</p>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={() => onCopy(item.url)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600">Copy</button>
                <button type="button" onClick={() => onDelete(item)} className="rounded-lg border border-red-200 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:text-red-300">Delete</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
