"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import Image from "next/image";
import QRCode from "qrcode";

type Scan = { country: string; device: string; scanned_at: string };
type DynamicCode = {
  id: string;
  code: string;
  name: string;
  target_url: string;
  enabled: boolean;
  scan_count: number;
  created_at?: string;
  scans?: Scan[];
  redirect_url?: string;
};

async function getCsrf(): Promise<string> {
  const response = await fetch("/api/auth/csrf", { credentials: "include" });
  if (!response.ok)
    throw new Error("Sign in before managing dynamic QR codes.");
  return ((await response.json()) as { csrf_token: string }).csrf_token;
}

export function DynamicQrManager() {
  const [codes, setCodes] = useState<DynamicCode[]>([]);
  const [images, setImages] = useState<Record<string, string>>({});
  const [name, setName] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(true);

  const refresh = useCallback(async () => {
    const response = await fetch("/api/business/dynamic-qr", {
      credentials: "include",
      cache: "no-store",
    });
    if (response.status === 401) {
      setSignedIn(false);
      return;
    }
    if (!response.ok) throw new Error("Could not load your dynamic QR codes.");
    const items = (await response.json()) as DynamicCode[];
    setCodes(items);
    const entries = await Promise.all(
      items.map(
        async (item) =>
          [
            item.id,
            await QRCode.toDataURL(`${window.location.origin}/q/${item.code}`, {
              width: 320,
              margin: 2,
              errorCorrectionLevel: "H",
            }),
          ] as const,
      ),
    );
    setImages(Object.fromEntries(entries));
  }, []);

  useEffect(() => {
    void refresh().catch((error: unknown) =>
      setMessage(
        error instanceof Error ? error.message : "Could not load QR codes.",
      ),
    );
  }, [refresh]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const token = await getCsrf();
      const response = await fetch(
        editing
          ? `/api/business/dynamic-qr/${editing}`
          : "/api/business/dynamic-qr",
        {
          method: editing ? "PUT" : "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
          body: JSON.stringify({ name, target_url: targetUrl }),
        },
      );
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok)
        throw new Error(payload.detail ?? "Could not save this QR code.");
      setName("");
      setTargetUrl("");
      setEditing(null);
      setMessage(
        "Your QR code was saved. Its printed code stays the same when you edit the destination.",
      );
      await refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Could not save this QR code.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(code: DynamicCode) {
    setBusy(true);
    setMessage("");
    try {
      const token = await getCsrf();
      const response = await fetch(`/api/business/dynamic-qr/${code.id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-RC-CSRF": token },
      });
      if (!response.ok) throw new Error("Could not delete this QR code.");
      await refresh();
      setMessage("QR code deleted.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not delete this QR code.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!signedIn) {
    return (
      <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
        <h2 className="text-xl font-semibold">
          Sign in to create a dynamic QR code
        </h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
          Dynamic destinations and scan analytics belong to your account.
        </p>
        <Link
          className="mt-4 inline-block rounded-xl bg-violet-600 px-5 py-3 font-semibold text-white"
          href="/login"
        >
          Sign in
        </Link>
      </section>
    );
  }

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
      <h2 className="text-xl font-semibold">Create an editable QR code</h2>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
        Your QR points to RenderCart first, so you can change its destination
        later. The destination is checked with Google Web Risk before it is
        saved.
      </p>
      <form className="mt-5 grid gap-4" onSubmit={(event) => void save(event)}>
        <label className="text-sm font-semibold">
          Name
          <input
            required
            maxLength={80}
            className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="text-sm font-semibold">
          Destination URL
          <input
            required
            type="url"
            maxLength={2048}
            className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
            placeholder="https://example.com/page"
            value={targetUrl}
            onChange={(event) => setTargetUrl(event.target.value)}
          />
        </label>
        <div className="flex gap-3">
          <button
            disabled={busy}
            className="rounded-xl bg-violet-600 px-5 py-3 font-semibold text-white disabled:opacity-50"
          >
            {busy ? "Saving…" : editing ? "Save destination" : "Create QR code"}
          </button>
          {editing && (
            <button
              type="button"
              className="rounded-xl border border-slate-300 px-4 py-3"
              onClick={() => {
                setEditing(null);
                setName("");
                setTargetUrl("");
              }}
            >
              Cancel edit
            </button>
          )}
        </div>
      </form>
      {message && (
        <p
          role="status"
          className="mt-4 text-sm text-slate-600 dark:text-slate-300"
        >
          {message}
        </p>
      )}
      <div className="mt-8 space-y-5">
        {codes.map((code) => (
          <article
            key={code.id}
            className="grid gap-5 rounded-xl border border-slate-200 p-4 sm:grid-cols-[160px_1fr] dark:border-slate-700"
          >
            {images[code.id] && (
              <Image
                src={images[code.id]}
                alt={`QR code for ${code.name}`}
                width={160}
                height={160}
                unoptimized
                className="h-40 w-40 bg-white p-2"
              />
            )}
            <div>
              <h3 className="font-semibold">{code.name}</h3>
              <p className="mt-1 break-all text-sm text-slate-600 dark:text-slate-300">
                {code.target_url}
              </p>
              <p className="mt-2 text-sm">
                {code.scan_count} scans · {code.enabled ? "Active" : "Disabled"}
              </p>
              <div className="mt-3 flex flex-wrap gap-4 text-sm font-semibold text-violet-700 dark:text-violet-300">
                <button
                  onClick={() => {
                    setEditing(code.id);
                    setName(code.name);
                    setTargetUrl(code.target_url);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  Edit destination
                </button>
                <a
                  href={images[code.id]}
                  download={`${code.name.replace(/[^a-z0-9_-]/giu, "-")}-qr.png`}
                >
                  Download QR
                </a>
                <button onClick={() => void remove(code)}>Delete</button>
              </div>
              {code.scans?.length ? (
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr>
                        <th className="py-1 pr-4">Scanned</th>
                        <th className="py-1 pr-4">Country</th>
                        <th className="py-1">Device</th>
                      </tr>
                    </thead>
                    <tbody>
                      {code.scans.slice(0, 10).map((scan, index) => (
                        <tr key={`${scan.scanned_at}-${index}`}>
                          <td className="py-1 pr-4">
                            {new Date(scan.scanned_at).toLocaleString()}
                          </td>
                          <td className="py-1 pr-4">{scan.country}</td>
                          <td className="py-1">{scan.device}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
