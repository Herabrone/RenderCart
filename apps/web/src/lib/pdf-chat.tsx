"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

type ChatTurn = {
  turn_id: string;
  job_id: string | null;
  question: string;
  answer: string | null;
  citations: { page: number; excerpt: string }[];
  status: "queued" | "running" | "succeeded" | "failed";
  error_code: string | null;
  created_at: string | null;
};

type ChatDocument = {
  document_id: string;
  indexed_job_id: string | null;
  filename: string;
  page_count: number;
  created_at: string | null;
  expires_at: string | null;
  turns: ChatTurn[];
};

async function getCsrfToken() {
  const response = await fetch("/api/auth/csrf", { credentials: "include", cache: "no-store" });
  if (!response.ok) throw new Error("Could not start a secure request.");
  return ((await response.json()) as { csrf_token: string }).csrf_token;
}

export function PdfChatPanel({ jobId }: { jobId?: string }) {
  const [documents, setDocuments] = useState<ChatDocument[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  const refresh = useCallback(async (): Promise<ChatDocument[]> => {
    const response = await fetch("/api/chat/documents", {
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Could not load your document chats.");
    const next = (await response.json()) as ChatDocument[];
    setDocuments(next);
    setSelectedId((current) => {
      if (current && next.some((document) => document.document_id === current)) return current;
      const indexed = jobId ? next.find((document) => document.indexed_job_id === jobId) : null;
      return indexed?.document_id ?? next[0]?.document_id ?? "";
    });
    return next;
  }, [jobId]);

  useEffect(() => {
    let live = true;
    void refresh()
      .catch((error: unknown) => {
        if (live) setMessage(error instanceof Error ? error.message : "Could not load chats.");
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => { live = false; };
  }, [refresh]);

  const selected = documents.find((document) => document.document_id === selectedId);
  const hasPending = documents.some((document) =>
    document.turns.some((turn) => turn.status === "queued" || turn.status === "running"),
  );

  useEffect(() => {
    if (!hasPending) return;
    const interval = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 1200);
    return () => window.clearInterval(interval);
  }, [hasPending, refresh]);

  async function askQuestion() {
    if (!selected || !question.trim() || busy) return;
    setBusy(true);
    setMessage("");
    try {
      const token = await getCsrfToken();
      const response = await fetch(`/api/chat/documents/${selected.document_id}/questions`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
        body: JSON.stringify({ question: question.trim() }),
      });
      const payload = (await response.json()) as { detail?: string; turn_id?: string };
      if (!response.ok || !payload.turn_id) {
        if (response.status === 402 && payload.detail?.includes("question limit")) {
          throw new Error("You’ve reached today’s free question limit. See plans for more access.");
        }
        if (response.status === 402) {
          throw new Error("You need more credits for this question. Open billing to buy a credit pack.");
        }
        throw new Error(payload.detail ?? "Could not send your question.");
      }
      setQuestion("");
      await refresh();
      for (let attempt = 0; attempt < 240; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const latest = await refresh();
        const current = latest.find((document) => document.document_id === selected.document_id);
        const turn = current?.turns.find((item) => item.turn_id === payload.turn_id);
        if (turn && turn.status !== "queued" && turn.status !== "running") break;
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not send your question.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteDocument(document: ChatDocument) {
    setMessage("");
    try {
      const token = await getCsrfToken();
      const response = await fetch(`/api/chat/documents/${document.document_id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-RC-CSRF": token },
      });
      if (!response.ok) throw new Error("Could not delete this document.");
      if (selectedId === document.document_id) setSelectedId("");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not delete this document.");
    }
  }

  return <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="text-xl font-semibold">Ask your document</h2>
        <p className="mt-1 text-sm text-slate-500">Answers are grounded in retrieved passages and include source pages.</p>
      </div>
      <Link href="/pricing" className="text-sm font-semibold text-violet-700 dark:text-violet-300">Plans and credits</Link>
    </div>

    {documents.length > 1 && <label className="mt-5 block text-sm font-medium">Document
      <select className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-600" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
        {documents.map((document) => <option key={document.document_id} value={document.document_id}>{document.filename} · {document.page_count} pages</option>)}
      </select>
    </label>}

    {!selected && (loading ? <p className="mt-5 text-sm text-slate-500">Loading documents…</p> : <p className="mt-5 text-sm text-slate-500">Your indexed documents will appear here. Upload a PDF above to start.</p>)}

    {selected && <>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 px-4 py-3 text-sm dark:bg-slate-800">
        <span><strong>{selected.filename}</strong> · {selected.page_count} pages</span>
        <button onClick={() => void deleteDocument(selected)} className="text-red-600 hover:underline">Delete chat and document</button>
      </div>

      <div className="mt-5 space-y-4">
        {selected.turns.map((turn) => <article key={turn.turn_id} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <p className="font-semibold">{turn.question}</p>
          {turn.status === "queued" || turn.status === "running" ? <p className="mt-2 text-sm text-slate-500">{turn.status === "queued" ? "Waiting for the AI worker…" : "Searching the document and writing an answer…"}</p> : null}
          {turn.status === "failed" && <p className="mt-2 text-sm text-red-600">Could not answer ({turn.error_code ?? "processing_failed"}). You were not charged for the failed question.</p>}
          {turn.answer && <p className="mt-3 whitespace-pre-wrap text-sm leading-7">{turn.answer}</p>}
          {turn.citations.length > 0 && <div className="mt-4 flex flex-wrap gap-2">{turn.citations.map((citation) => <details key={`${turn.turn_id}-${citation.page}`} className="rounded-lg bg-violet-50 px-3 py-2 text-xs dark:bg-violet-950">
            <summary className="cursor-pointer font-semibold">Page {citation.page}</summary>
            <p className="mt-2 max-w-xl leading-5 text-slate-600 dark:text-slate-300">{citation.excerpt}</p>
          </details>)}</div>}
        </article>)}
      </div>

      <form className="mt-5" onSubmit={(event) => { event.preventDefault(); void askQuestion(); }}>
        <label className="block text-sm font-semibold" htmlFor="pdf-chat-question">Your question</label>
        <textarea id="pdf-chat-question" maxLength={2000} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What are the main findings?" className="mt-2 min-h-24 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm dark:border-slate-600" />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500">Guest/free: one active document and 10 questions per day. Pro/day pass: 1 credit per question.</p>
          <button disabled={!question.trim() || busy} className="rounded-xl bg-violet-600 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Thinking…" : "Ask question"}</button>
        </div>
      </form>
    </>}
    {message && <p role="alert" className="mt-4 text-sm text-red-600">{message}</p>}
  </section>;
}
