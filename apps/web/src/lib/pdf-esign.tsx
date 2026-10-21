"use client";

import { useEffect, useRef, useState } from "react";

type PdfDocument = import("pdfjs-dist").PDFDocumentProxy;

export type ESignDraft = {
  signerName: string;
  signerEmail: string;
  pageNumber: number;
  consented: boolean;
  signaturePng: string;
  ready: boolean;
};

export function PdfESign({
  file,
  onChange,
}: {
  file: File | undefined;
  onChange: (draft: ESignDraft) => void;
}) {
  const previewRef = useRef<HTMLCanvasElement>(null);
  const signatureRef = useRef<HTMLCanvasElement>(null);
  const [document, setDocument] = useState<PdfDocument | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [signerName, setSignerName] = useState("");
  const [signerEmail, setSignerEmail] = useState("");
  const [consented, setConsented] = useState(false);
  const [hasSignature, setHasSignature] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let destroy: (() => void) | undefined;
    setDocument(null);
    setPageNumber(1);
    setHasSignature(false);
    setError("");
    if (!file) return;
    void (async () => {
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url,
        ).toString();
        const task = pdfjs.getDocument({ data: await file.arrayBuffer() });
        destroy = () => { void task.destroy(); };
        const loaded = await task.promise;
        if (cancelled) {
          destroy();
          return;
        }
        setDocument(loaded);
      } catch {
        if (!cancelled) setError("Could not preview this PDF. Try another PDF file.");
      }
    })();
    return () => {
      cancelled = true;
      destroy?.();
    };
  }, [file]);

  useEffect(() => {
    const canvas = previewRef.current;
    if (!canvas || !document) return;
    let cancelled = false;
    let renderTask: { cancel: () => void; promise: Promise<void> } | undefined;
    void document.getPage(pageNumber).then((page) => {
      if (cancelled) return;
      const base = page.getViewport({ scale: 1 });
      const viewport = page.getViewport({ scale: Math.min(1.2, 720 / base.width) });
      const context = canvas.getContext("2d", { alpha: false });
      if (!context) return;
      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);
      renderTask = page.render({ canvas, canvasContext: context, viewport });
      return renderTask.promise;
    }).catch(() => {
      if (!cancelled) setError("Could not render this PDF page.");
    });
    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [document, pageNumber]);

  useEffect(() => {
    const canvas = signatureRef.current;
    const context = canvas?.getContext("2d");
    if (context && canvas) {
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.lineWidth = 5;
      context.lineCap = "round";
      context.lineJoin = "round";
      context.strokeStyle = "#172554";
    }
    setHasSignature(false);
  }, [file, pageNumber]);

  useEffect(() => {
    const canvas = signatureRef.current;
    const signaturePng = hasSignature && canvas ? canvas.toDataURL("image/png") : "";
    onChange({
      signerName,
      signerEmail,
      pageNumber,
      consented,
      signaturePng,
      ready: !!file && !!document && hasSignature && !!signerName.trim() &&
        /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(signerEmail) && consented,
    });
  }, [consented, document, file, hasSignature, onChange, pageNumber, signerEmail, signerName]);

  function point(event: React.PointerEvent<HTMLCanvasElement>) {
    const canvas = event.currentTarget;
    const bounds = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - bounds.left) * canvas.width / bounds.width,
      y: (event.clientY - bounds.top) * canvas.height / bounds.height,
    };
  }

  function startDrawing(event: React.PointerEvent<HTMLCanvasElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    const context = event.currentTarget.getContext("2d");
    const location = point(event);
    context?.beginPath();
    context?.moveTo(location.x, location.y);
    context?.lineTo(location.x + 0.1, location.y + 0.1);
    context?.stroke();
    setHasSignature(true);
  }

  function draw(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
    const location = point(event);
    const context = event.currentTarget.getContext("2d");
    context?.lineTo(location.x, location.y);
    context?.stroke();
    setHasSignature(true);
  }

  function clearSignature() {
    const canvas = signatureRef.current;
    canvas?.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
    setHasSignature(false);
  }

  return <section className="mt-5 rounded-xl border border-slate-200 p-4 dark:border-slate-700" aria-label="Sign PDF">
    <h2 className="font-semibold">Add your visual signature</h2>
    <p className="mt-1 text-sm text-slate-500">Draw in the marked area. This creates a visual mark and audit record, not a certificate-backed digital signature.</p>
    {!file && <p className="mt-4 text-sm text-slate-500">Choose a PDF to preview and sign it.</p>}
    {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
    {document && <div className="mt-4 flex items-center justify-between gap-3">
      <label className="text-sm font-medium">Signature page
        <select className="ml-2 rounded-lg border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-600" value={pageNumber} onChange={(event) => setPageNumber(Number(event.target.value))}>
          {Array.from({ length: document.numPages }, (_, index) => <option key={index + 1} value={index + 1}>Page {index + 1}</option>)}
        </select>
      </label>
      <button type="button" onClick={clearSignature} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600">Clear signature</button>
    </div>}
    {document && <div className="mt-3 flex justify-center overflow-auto rounded-lg bg-slate-100 p-3 dark:bg-slate-800">
      <div className="relative inline-block max-w-full shadow">
        <canvas ref={previewRef} className="block h-auto max-w-full bg-white" />
        <div className="pointer-events-none absolute bottom-[8%] left-[8%] flex h-[15%] w-[42%] flex-col border border-dashed border-violet-500/70 bg-violet-100/35 p-1 text-[10px] text-violet-800">
          <span className="pointer-events-none">Draw signature here</span>
        </div>
        <canvas ref={signatureRef} width={900} height={180} aria-label="Draw signature" onPointerDown={startDrawing} onPointerMove={draw} className="absolute bottom-[8%] left-[8%] h-[15%] w-[42%] touch-none cursor-crosshair" />
      </div>
    </div>}
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <label className="text-sm font-semibold">Signer name
        <input required maxLength={120} autoComplete="name" value={signerName} onChange={(event) => setSignerName(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600" />
      </label>
      <label className="text-sm font-semibold">Signer email
        <input required type="email" autoComplete="email" value={signerEmail} onChange={(event) => setSignerEmail(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600" />
      </label>
    </div>
    <label className="mt-4 flex items-start gap-2 text-sm">
      <input type="checkbox" checked={consented} onChange={(event) => setConsented(event.target.checked)} className="mt-1 accent-violet-600" />
      <span>I intend to sign this document electronically and consent to recording my name, email, IP address, signing time, and document hashes in the audit record.</span>
    </label>
  </section>;
}
