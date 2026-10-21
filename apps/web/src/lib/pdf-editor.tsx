"use client";

import { useEffect, useRef, useState } from "react";

type PdfDocument = import("pdfjs-dist").PDFDocumentProxy;

export type PdfEditText = { page: number; x: number; y: number; text: string };
export type PdfEditImage = { page: number; x: number; y: number; dataUrl: string; mime: "image/png" | "image/jpeg" };
export type PdfEditField = { name: string; kind: "text" | "checkbox" | "choice"; value: string; options: string[] };
export type PdfEditDraft = {
  texts: PdfEditText[];
  images: PdfEditImage[];
  fields: PdfEditField[];
  ready: boolean;
};

function readDataUrl(dataUrl: string): Uint8Array {
  const encoded = dataUrl.split(",")[1] ?? "";
  return Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0));
}

export async function createEditedPdf(file: File, draft: PdfEditDraft): Promise<File> {
  const pdfLib = await import("pdf-lib");
  const pdf = await pdfLib.PDFDocument.load(await file.arrayBuffer());
  const font = await pdf.embedFont(pdfLib.StandardFonts.Helvetica);
  const form = pdf.getForm();
  for (const fieldDraft of draft.fields) {
    const field = form.getField(fieldDraft.name);
    if (field instanceof pdfLib.PDFTextField) field.setText(fieldDraft.value);
    else if (field instanceof pdfLib.PDFCheckBox) {
      if (fieldDraft.value === "true") field.check();
      else field.uncheck();
    } else if (field instanceof pdfLib.PDFDropdown || field instanceof pdfLib.PDFOptionList || field instanceof pdfLib.PDFRadioGroup) {
      if (fieldDraft.value) field.select(fieldDraft.value);
    }
  }
  for (const mark of draft.texts) {
    const page = pdf.getPage(mark.page - 1);
    const size = page.getSize();
    page.drawText(mark.text, {
      x: mark.x * size.width,
      y: mark.y * size.height,
      size: 14,
      font,
      color: pdfLib.rgb(0.08, 0.12, 0.22),
      maxWidth: size.width * 0.7,
    });
  }
  for (const mark of draft.images) {
    const page = pdf.getPage(mark.page - 1);
    const size = page.getSize();
    const imageBytes = readDataUrl(mark.dataUrl);
    const image = mark.mime === "image/png" ? await pdf.embedPng(imageBytes) : await pdf.embedJpg(imageBytes);
    const width = Math.min(size.width * 0.3, size.width * (1 - mark.x));
    const height = Math.min(width * image.height / image.width, size.height * (1 - mark.y));
    page.drawImage(image, { x: mark.x * size.width, y: mark.y * size.height, width, height });
  }
  const bytes = await pdf.save();
  const name = file.name.replace(/\.pdf$/i, "") || "document";
  return new File([new Uint8Array(bytes)], `${name}-edited.pdf`, { type: "application/pdf" });
}

export function PdfEditor({
  file,
  onChange,
}: {
  file: File | undefined;
  onChange: (draft: PdfEditDraft) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [document, setDocument] = useState<PdfDocument | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [texts, setTexts] = useState<PdfEditText[]>([]);
  const [images, setImages] = useState<PdfEditImage[]>([]);
  const [fields, setFields] = useState<PdfEditField[]>([]);
  const [textValue, setTextValue] = useState("");
  const [activeMode, setActiveMode] = useState<"text" | "image">("text");
  const [imageValue, setImageValue] = useState<PdfEditImage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let destroy: (() => void) | undefined;
    setDocument(null);
    setPageNumber(1);
    setTexts([]);
    setImages([]);
    setFields([]);
    setImageValue(null);
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
        const pdfLib = await import("pdf-lib");
        const editable = await pdfLib.PDFDocument.load(await file.arrayBuffer());
        const foundFields: PdfEditField[] = [];
        for (const field of editable.getForm().getFields()) {
          if (field instanceof pdfLib.PDFTextField) {
            foundFields.push({ name: field.getName(), kind: "text", value: field.getText() ?? "", options: [] });
          } else if (field instanceof pdfLib.PDFCheckBox) {
            foundFields.push({ name: field.getName(), kind: "checkbox", value: String(field.isChecked()), options: [] });
          } else if (field instanceof pdfLib.PDFDropdown || field instanceof pdfLib.PDFOptionList || field instanceof pdfLib.PDFRadioGroup) {
            const selected = field.getSelected();
            foundFields.push({ name: field.getName(), kind: "choice", value: Array.isArray(selected) ? selected[0] ?? "" : selected ?? "", options: field.getOptions() });
          }
        }
        if (!cancelled) setFields(foundFields);
      } catch {
        if (!cancelled) setError("Could not read this PDF. Try another PDF file.");
      }
    })();
    return () => {
      cancelled = true;
      destroy?.();
    };
  }, [file]);

  useEffect(() => {
    const canvas = canvasRef.current;
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
    onChange({ texts, images, fields, ready: !!file && !!document });
  }, [document, fields, file, images, onChange, texts]);

  async function chooseImage(fileImage: File | undefined) {
    if (!fileImage || !["image/png", "image/jpeg"].includes(fileImage.type)) {
      setImageValue(null);
      return;
    }
    if (fileImage.size > 10 * 1024 * 1024) {
      setError("Choose a PNG or JPEG image smaller than 10 MB.");
      setImageValue(null);
      return;
    }
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => typeof reader.result === "string" ? resolve(reader.result) : reject(new Error("read_failed"));
      reader.onerror = () => reject(new Error("read_failed"));
      reader.readAsDataURL(fileImage);
    });
    setError("");
    setImageValue({ page: pageNumber, x: 0.08, y: 0.72, dataUrl, mime: fileImage.type as "image/png" | "image/jpeg" });
  }

  function placeOnPage(event: React.MouseEvent<HTMLCanvasElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(0.95, (event.clientX - bounds.left) / bounds.width));
    const y = Math.max(0, Math.min(0.95, 1 - (event.clientY - bounds.top) / bounds.height));
    if (activeMode === "text") {
      if (!textValue.trim()) {
        setError("Enter text before placing it on the page.");
        return;
      }
      setTexts((current) => [...current, { page: pageNumber, x, y, text: textValue.trim().slice(0, 500) }]);
    } else if (imageValue) {
      setImages((current) => [...current, { ...imageValue, page: pageNumber, x, y }]);
    } else {
      setError("Choose a PNG or JPEG image before placing it.");
    }
    setError("");
  }

  function updateField(name: string, value: string) {
    setFields((current) => current.map((field) => field.name === name ? { ...field, value } : field));
  }

  return <section className="mt-5 rounded-xl border border-slate-200 p-4 dark:border-slate-700" aria-label="Edit PDF">
    <h2 className="font-semibold">Edit your PDF</h2>
    <p className="mt-1 text-sm text-slate-500">Add text or an image by choosing a mode and clicking on the page. Existing printed text is not rewritten. Free downloads have a RenderCart preview watermark.</p>
    {!file && <p className="mt-4 text-sm text-slate-500">Choose a PDF to start editing.</p>}
    {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
    {document && <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
      <label className="text-sm font-medium">Page
        <select className="ml-2 rounded-lg border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-600" value={pageNumber} onChange={(event) => setPageNumber(Number(event.target.value))}>
          {Array.from({ length: document.numPages }, (_, index) => <option key={index + 1} value={index + 1}>Page {index + 1}</option>)}
        </select>
      </label>
      <div className="flex gap-2">
        <button type="button" aria-pressed={activeMode === "text"} onClick={() => setActiveMode("text")} className={`rounded-lg border px-3 py-1.5 text-sm ${activeMode === "text" ? "border-violet-500 text-violet-700" : "border-slate-300 dark:border-slate-600"}`}>Place text</button>
        <button type="button" aria-pressed={activeMode === "image"} onClick={() => setActiveMode("image")} className={`rounded-lg border px-3 py-1.5 text-sm ${activeMode === "image" ? "border-violet-500 text-violet-700" : "border-slate-300 dark:border-slate-600"}`}>Place image</button>
      </div>
    </div>}
    {document && <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto]">
      <input aria-label="Text to add" maxLength={500} value={textValue} onChange={(event) => setTextValue(event.target.value)} placeholder="Text to place on the PDF" className="rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-600" />
      <label className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600">PNG/JPEG image
        <input type="file" accept="image/png,image/jpeg" className="ml-2 max-w-48 text-xs" onChange={(event) => void chooseImage(event.target.files?.[0])} />
      </label>
    </div>}
    {imageValue && <p className="mt-2 text-xs text-slate-500">Selected image: ready to place at a click. Select a different image to replace it.</p>}
    {document && <div className="mt-3 flex justify-center overflow-auto rounded-lg bg-slate-100 p-3 dark:bg-slate-800">
      <div className="relative inline-block max-w-full shadow">
        <canvas ref={canvasRef} onClick={placeOnPage} aria-label={`PDF page ${pageNumber}, click to place the selected item`} className="block h-auto max-w-full cursor-crosshair bg-white" />
        <div className="pointer-events-none absolute inset-0">
          {texts.filter((item) => item.page === pageNumber).map((item, index) => <span key={`text-${index}`} className="absolute max-w-[70%] truncate border border-violet-400 bg-white/75 px-1 text-sm text-slate-900" style={{ left: `${item.x * 100}%`, top: `${(1 - item.y) * 100}%` }}>{item.text}</span>)}
          {images.filter((item) => item.page === pageNumber).map((item, index) => <span key={`image-${index}`} className="absolute border border-violet-400 bg-violet-200/50 px-2 py-1 text-xs text-violet-950" style={{ left: `${item.x * 100}%`, top: `${(1 - item.y) * 100}%` }}>Image</span>)}
        </div>
      </div>
    </div>}
    {document && <p className="mt-2 text-xs text-slate-500">Text marks: {texts.length} · Image marks: {images.length}</p>}
    {document && fields.length > 0 && <div className="mt-5 rounded-lg bg-slate-50 p-3 dark:bg-slate-800">
      <h3 className="font-medium">Fill PDF form fields</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {fields.map((field) => <label key={field.name} className="text-sm font-medium">{field.name}
          {field.kind === "checkbox" ? <input type="checkbox" checked={field.value === "true"} onChange={(event) => updateField(field.name, String(event.target.checked))} className="ml-2 accent-violet-600" /> : field.kind === "choice" ? <select value={field.value} onChange={(event) => updateField(field.name, event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 bg-transparent px-2 py-2 dark:border-slate-600"><option value="">Choose…</option>{field.options.map((option) => <option key={option} value={option}>{option}</option>)}</select> : <input value={field.value} onChange={(event) => updateField(field.name, event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 bg-transparent px-2 py-2 dark:border-slate-600" />}
        </label>)}
      </div>
    </div>}
    {document && fields.length === 0 && <p className="mt-3 text-xs text-slate-500">No supported interactive form fields were found in this PDF.</p>}
  </section>;
}
