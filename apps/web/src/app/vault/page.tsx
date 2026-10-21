import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import VaultManager from "@/lib/vault-manager";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Vault | RenderCart",
  robots: { index: false, follow: false },
};

export default async function VaultPage() {
  const session = (await cookies()).get("rc_session");
  if (!session) notFound();
  let authorized = false;
  try {
    const response = await fetch(
      `${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/vault/session`,
      { headers: { cookie: `${session.name}=${session.value}` }, cache: "no-store" },
    );
    authorized = response.ok;
  } catch {
    authorized = false;
  }
  if (!authorized) notFound();

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-10">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-600">Private owner tools</p>
      <h1 className="mt-3 text-3xl font-bold">Vault</h1>
      <p className="mt-2 max-w-2xl text-slate-600 dark:text-slate-300">
        Temporary links and text shares are encrypted at rest and expire automatically.
      </p>
      <VaultManager />
    </main>
  );
}
