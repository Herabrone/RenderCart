import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { JobRunner } from "@/lib/job-runner";
export async function generateMetadata() {
  return { title: "Job status & results | RenderCart" };
}
export default async function JobPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;
  return (
    <main className="job-page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/tools">All tools</Link>
        <ChevronRight size={12} />
        <span>Job status</span>
      </nav>
      <span className="eyebrow">Your work, in progress</span>
      <h1>Your job.</h1>
      <p className="mt-3 text-muted">
        Track the progress and collect your result here.
      </p>
      <JobRunner jobId={jobId} />
    </main>
  );
}
