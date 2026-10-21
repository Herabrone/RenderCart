"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { authPost, AuthResponse } from "@/lib/auth";

export default function SignupPage() {
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [turnstileSiteKey, setTurnstileSiteKey] = useState<string | null>(null);
  const [turnstileToken, setTurnstileToken] = useState("");

  useEffect(() => {
    void fetch("/api/security/config", { cache: "no-store" })
      .then(
        (response) =>
          response.json() as Promise<{ turnstile_site_key: string | null }>,
      )
      .then((config) => setTurnstileSiteKey(config.turnstile_site_key))
      .catch(() => setTurnstileSiteKey(null));
  }, []);

  useEffect(() => {
    if (!turnstileSiteKey) return;
    type Api = {
      render: (
        element: HTMLElement,
        options: {
          sitekey: string;
          callback: (token: string) => void;
          "expired-callback": () => void;
        },
      ) => string;
      reset?: (id?: string) => void;
    };
    type TurnstileWindow = Window & { turnstile?: Api };
    const widget = document.getElementById("signup-turnstile");
    if (!widget) return;
    let widgetId: string | undefined;
    let attempts = 0;
    const render = () => {
      const api = (window as TurnstileWindow).turnstile;
      if (!api) {
        if (++attempts < 20) window.setTimeout(render, 250);
        return;
      }
      widgetId = api.render(widget, {
        sitekey: turnstileSiteKey,
        callback: setTurnstileToken,
        "expired-callback": () => setTurnstileToken(""),
      });
    };
    const script = document.createElement("script");
    script.src =
      "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.nonce =
      document.querySelector<HTMLScriptElement>("script[nonce]")?.nonce ?? "";
    script.async = true;
    script.defer = true;
    script.onload = render;
    document.head.appendChild(script);
    return () => {
      const api = (window as TurnstileWindow).turnstile as
        (Api & { remove?: (id: string) => void }) | undefined;
      if (widgetId) api?.remove?.(widgetId);
      script.remove();
    };
  }, [turnstileSiteKey]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const data = new FormData(event.currentTarget);
    const displayName = String(data.get("display_name") ?? "").trim();
    try {
      const address = String(data.get("email"));
      await authPost<AuthResponse>("signup", {
        email: address,
        password: String(data.get("password")),
        ...(turnstileToken ? { turnstile_token: turnstileToken } : {}),
        ...(displayName ? { display_name: displayName } : {}),
      });
      setEmail(address);
      setComplete(true);
    } catch (cause) {
      if (turnstileToken) {
        type TurnstileWindow = Window & { turnstile?: { reset?: () => void } };
        (window as TurnstileWindow).turnstile?.reset?.();
        setTurnstileToken("");
      }
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not create your account.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
      <section className="rounded-3xl border border-line bg-surface p-8 shadow-sm  ">
        {complete ? (
          <div role="status">
            <h1 className="text-2xl font-semibold">Check your inbox</h1>
            <p className="mt-3 text-muted ">
              We sent a verification link to {email}. Use it to finish setting
              up your account.
            </p>
            <button
              type="button"
              onClick={async () => {
                try {
                  await authPost("verify-email/request", { email });
                } catch {
                  /* Keep the original confirmation to avoid exposing account status. */
                }
              }}
              className="mt-4 text-sm font-medium text-accent "
            >
              Send another verification link
            </button>
          </div>
        ) : (
          <>
            <h1 className="text-2xl font-semibold">Create your account</h1>
            <p className="mt-2 text-sm text-muted ">
              Save your work and get more from RenderCart tools.
            </p>
            <form className="mt-7 space-y-4" onSubmit={submit}>
              <label className="block text-sm font-medium">
                Name <span className="font-normal text-muted">(optional)</span>
                <input
                  name="display_name"
                  autoComplete="name"
                  maxLength={120}
                  className="mt-1 w-full rounded-xl border border-line-strong bg-transparent px-3 py-2.5 "
                />
              </label>
              <label className="block text-sm font-medium">
                Email
                <input
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  className="mt-1 w-full rounded-xl border border-line-strong bg-transparent px-3 py-2.5 "
                />
              </label>
              <label className="block text-sm font-medium">
                Password
                <input
                  aria-describedby="password-hint"
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  minLength={10}
                  required
                  className="mt-1 w-full rounded-xl border border-line-strong bg-transparent px-3 py-2.5 "
                />
              </label>
              <p id="password-hint" className="text-xs text-muted">
                Use at least 10 characters.
              </p>
              {turnstileSiteKey && <div id="signup-turnstile" />}
              {error && (
                <p role="alert" className="text-sm text-red-600">
                  {error}
                </p>
              )}
              <button
                disabled={busy || (!!turnstileSiteKey && !turnstileToken)}
                className="w-full rounded-xl bg-accent px-4 py-3 font-medium text-white disabled:opacity-60"
              >
                {busy ? "Creating account…" : "Create account"}
              </button>
            </form>
            <div className="mt-5 text-center text-sm text-muted ">
              Already registered?{" "}
              <Link className="font-medium text-accent " href="/login">
                Sign in
              </Link>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
