import type { Metadata } from "next";
import { connection } from "next/server";
import { Analytics } from "@/lib/analytics";
import { AppFrame } from "@/components/app-frame";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.APP_BASE_URL ?? "https://rendercart.app"),
  title: "RenderCart — Useful tools, all in one place",
  description:
    "A growing collection of practical file, creative, business, and developer tools.",
  icons: { icon: "/icon.svg" },
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // Request rendering keeps the framework scripts compatible with the nonce CSP.
  await connection();
  return (
    <html lang="en">
      <body>
        <AppFrame>{children}</AppFrame>
        <Analytics
          websiteId={process.env.UMAMI_WEBSITE_ID ?? ""}
          baseUrl={process.env.UMAMI_BASE_URL ?? ""}
        />
      </body>
    </html>
  );
}
