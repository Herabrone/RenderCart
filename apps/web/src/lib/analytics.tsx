"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

declare global {
  interface Window {
    umami?: {
      track: (eventName?: string, eventData?: Record<string, string | number | boolean>) => void;
    };
  }
}

const privatePathPrefixes = [
  "/account",
  "/admin",
  "/api",
  "/auth",
  "/jobs",
  "/vault",
  "/v/",
  "/p/",
  "/f/",
];

function isTrackablePath(pathname: string): boolean {
  return !privatePathPrefixes.some(
    (prefix) => pathname === prefix || pathname.startsWith(prefix),
  );
}

export function trackRenderCartEvent(
  eventName: string,
  eventData?: Record<string, string | number | boolean>,
) {
  if (typeof window === "undefined" || !isTrackablePath(window.location.pathname)) return;
  window.umami?.track(eventName, eventData);
}

export function Analytics({ websiteId, baseUrl }: { websiteId: string; baseUrl: string }) {
  const pathname = usePathname();
  const [scriptEnabled, setScriptEnabled] = useState(false);
  const [nonce, setNonce] = useState("");
  const trackedPath = useRef<string | null>(null);
  const checkoutSuccess =
    pathname === "/account/billing" &&
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).get("status") === "success";

  useEffect(() => {
    setNonce(document.querySelector<HTMLScriptElement>("script[nonce]")?.nonce ?? "");
    const allowed = Boolean(websiteId) && (isTrackablePath(pathname) || checkoutSuccess);
    setScriptEnabled(allowed);
    if (allowed && isTrackablePath(pathname) && window.umami && trackedPath.current !== pathname) {
      trackedPath.current = pathname;
      window.umami.track();
    }
  }, [checkoutSuccess, pathname, websiteId]);

  if (!scriptEnabled || !websiteId || !nonce) return null;
  return (
    <Script
      id="rendercart-umami"
      src={`${baseUrl.replace(/\/$/, "")}/script.js`}
      strategy="afterInteractive"
      nonce={nonce}
      data-website-id={websiteId}
      data-host-url={baseUrl.replace(/\/$/, "")}
      data-auto-track="false"
      data-exclude-search="true"
      data-exclude-hash="true"
      data-do-not-track="true"
      onReady={() => {
        if (isTrackablePath(pathname) && window.umami && trackedPath.current !== pathname) {
          trackedPath.current = pathname;
          window.umami.track();
        }
        if (!checkoutSuccess || !window.umami) return;
        const sessionId = new URLSearchParams(window.location.search).get("session_id");
        const key = sessionId ? `rendercart-analytics-conversion:${sessionId}` : "";
        if (key && sessionStorage.getItem(key)) return;
        if (key) sessionStorage.setItem(key, "1");
        window.umami.track("purchase-complete");
      }}
    />
  );
}
