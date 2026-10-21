import Link from "next/link";
import { JobRunner } from "@/lib/job-runner";

export async function generateMetadata() { return { title: "Processing your file | RenderCart" }; }

export default async function JobPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return <main className="mx-auto min-h-screen max-w-3xl px-6 py-10">
    <Link href="/tools" className="font-bold">RenderCart</Link>
    <h1 className="mt-16 text-4xl font-semibold">Your file is processing</h1>
    <p className="mt-3 text-slate-600 dark:text-slate-300">Keep this page open. Your result will appear here when it is ready.</p>
    <JobRunner jobId={jobId} />
  </main>;
}
