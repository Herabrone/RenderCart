import type { Metadata } from "next";
import { Analytics } from "@/lib/analytics";
import "./globals.css";

export const metadata: Metadata = {
  title: "RenderCart — Useful tools, all in one place",
  description: "A growing collection of practical file, creative, business, and developer tools.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {children}
        <Analytics
          websiteId={process.env.UMAMI_WEBSITE_ID ?? ""}
          baseUrl={process.env.UMAMI_BASE_URL ?? ""}
        />
      </body>
    </html>
  );
}
