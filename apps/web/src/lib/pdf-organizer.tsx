"use client";

import { useEffect, useState } from "react";

type PdfDocument = import("pdfjs-dist").PDFDocumentProxy;

function PageThumbnail({
  document,
  pageNumber,
}: {
  document: PdfDocument;
  pageNumber: number;
}) {
  const [canvas, setCanvas] = useState<HTMLCanvasElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!canvas) return;
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      {
        rootMargin: "160px",
      },
    );
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [canvas]);

  useEffect(() => {
    if (!canvas || !visible) return;
    let cancelled = false;
    let renderTask: { cancel: () => void; promise: Promise<void> } | undefined;
    void document
      .getPage(pageNumber)
      .then((page) => {
        if (cancelled) return;
        const pageViewport = page.getViewport({ scale: 1 });
        const viewport = page.getViewport({
          scale: Math.min(1, 180 / pageViewport.width),
        });
        const context = canvas.getContext("2d", { alpha: false });
        if (!context) return;
        canvas.width = Math.ceil(viewport.width);
        canvas.height = Math.ceil(viewport.height);
        renderTask = page.render({ canvas, canvasContext: context, viewport });
        return renderTask.promise;
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      renderTask?.cancel();
      canvas.width = 0;
      canvas.height = 0;
    };
  }, [canvas, document, pageNumber, visible]);

  return (
    <canvas
      ref={setCanvas}
      aria-label={`Preview of page ${pageNumber}`}
      className="max-h-60 max-w-full rounded bg-surface shadow-sm"
    />
  );
}

export function PdfOrganizer({
  file,
  onOrderChange,
  onReadyChange,
}: {
  file: File | undefined;
  onOrderChange: (pageOrder: string) => void;
  onReadyChange: (ready: boolean) => void;
}) {
  const [document, setDocument] = useState<PdfDocument | null>(null);
  const [pages, setPages] = useState<number[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let destroyLoadingTask: (() => void) | undefined;
    setDocument(null);
    setPages([]);
    setError("");
    onOrderChange("");
    onReadyChange(false);
    if (!file) return;

    void (async () => {
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url,
        ).toString();
        const loadingTask = pdfjs.getDocument({
          data: await file.arrayBuffer(),
        });
        destroyLoadingTask = () => {
          void loadingTask.destroy();
        };
        const loaded = await loadingTask.promise;
        if (cancelled) {
          destroyLoadingTask();
          return;
        }
        setDocument(loaded);
        const order = Array.from(
          { length: loaded.numPages },
          (_, index) => index + 1,
        );
        setPages(order);
        onReadyChange(true);
      } catch {
        if (!cancelled) {
          setError(
            "Could not read this PDF in the browser. Try another PDF file.",
          );
          onReadyChange(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      destroyLoadingTask?.();
    };
  }, [file, onOrderChange, onReadyChange]);

  useEffect(() => {
    onOrderChange(pages.join(", "));
  }, [onOrderChange, pages]);

  function movePage(index: number, offset: -1 | 1) {
    setPages((current) => {
      const destination = index + offset;
      if (destination < 0 || destination >= current.length) return current;
      const next = [...current];
      [next[index], next[destination]] = [next[destination], next[index]];
      return next;
    });
  }

  function removePage(index: number) {
    setPages((current) => {
      if (current.length <= 1) return current;
      const next = current.filter((_, pageIndex) => pageIndex !== index);
      return next;
    });
  }

  return (
    <section
      className="mt-5 rounded-xl border border-line p-4 "
      aria-label="Organize PDF pages"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">Arrange pages</h2>
          <p className="mt-1 text-sm text-muted">
            Move pages with the arrows or remove pages you do not need.
          </p>
        </div>
        {document && (
          <p className="text-sm text-muted">
            {pages.length} of {document.numPages} pages selected
          </p>
        )}
      </div>
      {!file && (
        <p className="mt-4 text-sm text-muted">
          Choose a PDF to see its page previews.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-4 text-sm text-red-600">
          {error}
        </p>
      )}
      {file && !document && !error && (
        <p className="mt-4 text-sm text-muted">Loading page previews…</p>
      )}
      {document && (
        <ol className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {pages.map((pageNumber, index) => (
            <li
              key={pageNumber}
              className="min-w-0 rounded-lg border border-line p-2 "
            >
              <div className="flex h-44 items-center justify-center overflow-hidden rounded bg-subtle p-2 ">
                <PageThumbnail document={document} pageNumber={pageNumber} />
              </div>
              <p className="mt-2 truncate text-center text-xs font-medium">
                Page {pageNumber}
              </p>
              <div className="mt-2 flex justify-center gap-1">
                <button
                  type="button"
                  aria-label={`Move page ${pageNumber} up`}
                  title="Move earlier"
                  disabled={index === 0}
                  onClick={() => movePage(index, -1)}
                  className="rounded-md border border-line-strong px-2 py-1 text-sm disabled:opacity-40 "
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Move page ${pageNumber} down`}
                  title="Move later"
                  disabled={index === pages.length - 1}
                  onClick={() => movePage(index, 1)}
                  className="rounded-md border border-line-strong px-2 py-1 text-sm disabled:opacity-40 "
                >
                  ↓
                </button>
                <button
                  type="button"
                  aria-label={`Remove page ${pageNumber}`}
                  title="Remove page"
                  disabled={pages.length <= 1}
                  onClick={() => removePage(index)}
                  className="rounded-md border border-red-200 px-2 py-1 text-sm text-red-700 disabled:opacity-40  "
                >
                  ×
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
