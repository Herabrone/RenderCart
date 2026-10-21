"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { PdfOrganizer } from "@/lib/pdf-organizer";
import { ESignDraft, PdfESign } from "@/lib/pdf-esign";
import { createEditedPdf, PdfEditDraft, PdfEditor } from "@/lib/pdf-editor";
import { VideoTrimmer } from "@/lib/video-trimmer";
import { PdfChatPanel } from "@/lib/pdf-chat";
import { trackRenderCartEvent } from "@/lib/analytics";

type ToolInfo = {
  slug: string;
  name: string;
  summary: string;
  runtime?: string;
  batchable?: boolean;
  batch_max_files?: number | null;
  inputs: { accept: string[]; min_files: number } | null;
  job_tier?: "S" | "M" | "L" | null;
  single_job_price_cents?: number | null;
  prices?: Record<string, number>;
  options_schema: {
    properties?: Record<
      string,
      {
        default?: unknown;
        description?: string;
        enum?: string[];
        format?: string;
        maximum?: number;
        minimum?: number;
        title?: string;
        type?: string;
        widget?: string;
        maxLength?: number;
        minLength?: number;
      }
    >;
  } | null;
};

type JobInfo = {
  job_id: string;
  state: string;
  progress: number;
  download_url?: string;
  error_code?: string;
  locked_preview?: boolean;
  tool_slug?: string;
  can_unlock?: boolean;
  payment_product?: "job_s" | "job_m" | "job_l";
};

type InvoiceDraft = {
  document_type: "invoice" | "quote" | "receipt";
  number: string;
  currency: string;
  issued_on: string;
  due_on: string;
  business_name: string;
  business_email: string;
  business_address: string;
  client_name: string;
  client_email: string;
  client_address: string;
  notes: string;
  tax_percent: string;
};

type SavedClient = {
  id: string;
  name: string;
  email: string;
  address: string;
};

type SavedInvoiceItem = {
  id: string;
  description: string;
  unit_price: string;
};

type RecurringInvoice = {
  id: string;
  interval: "weekly" | "monthly";
  active: boolean;
  next_run_at: string;
  last_job_id: string | null;
};

type BusinessCardDraft = {
  name: string;
  title: string;
  company: string;
  email: string;
  phone: string;
  website: string;
  accent_color: string;
};

type ResumeDraft = {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  website: string;
  summary: string;
  experience: string;
  education: string;
  skills: string;
  cover_letter: string;
};

type ResumeTemplate = "classic" | "modern" | "compact";

async function csrfToken() {
  const response = await fetch("/api/auth/csrf", { credentials: "include" });
  if (!response.ok) throw new Error("Could not start a secure request.");
  return ((await response.json()) as { csrf_token: string }).csrf_token;
}

function uploadContentType(toolSlug: string, file: File): string {
  if (toolSlug === "document-translator") {
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (extension === "pdf") return "application/pdf";
    if (extension === "docx")
      return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    if (extension === "pptx")
      return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
    if (extension === "txt") return "text/plain";
  }
  if (toolSlug === "subtitle-translation") {
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (extension === "srt") return "application/x-subrip";
    if (extension === "vtt") return "text/vtt";
  }
  return file.type || "application/octet-stream";
}

export function JobRunner({
  tool,
  jobId,
}: {
  tool?: ToolInfo;
  jobId?: string;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [optionValues, setOptionValues] = useState<Record<string, string>>({});
  const [turnstileSiteKey, setTurnstileSiteKey] = useState<string | null>(null);
  const [turnstileToken, setTurnstileToken] = useState("");
  const [job, setJob] = useState<JobInfo | null>(null);
  const [uploadedIds, setUploadedIds] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [paywall, setPaywall] = useState(false);
  const [busy, setBusy] = useState(false);
  const [batchMode, setBatchMode] = useState(false);
  const [pdfReady, setPdfReady] = useState(false);
  const [esignDraft, setEsignDraft] = useState<ESignDraft | null>(null);
  const [pdfEditDraft, setPdfEditDraft] = useState<PdfEditDraft | null>(null);
  const [videoTrimReady, setVideoTrimReady] = useState(false);
  const [invoiceDraft, setInvoiceDraft] = useState<InvoiceDraft>({
    document_type: "invoice",
    number: "INV-001",
    currency: "CAD",
    issued_on: "",
    due_on: "",
    business_name: "",
    business_email: "",
    business_address: "",
    client_name: "",
    client_email: "",
    client_address: "",
    notes: "",
    tax_percent: "0",
  });
  const [invoiceItems, setInvoiceItems] = useState([
    { description: "", quantity: "1", unit_price: "0" },
  ]);
  const [savedClients, setSavedClients] = useState<SavedClient[]>([]);
  const [savedInvoiceItems, setSavedInvoiceItems] = useState<
    SavedInvoiceItem[]
  >([]);
  const [invoiceSaveMessage, setInvoiceSaveMessage] = useState("");
  const [recurringInvoices, setRecurringInvoices] = useState<
    RecurringInvoice[]
  >([]);
  const [businessCard, setBusinessCard] = useState<BusinessCardDraft>({
    name: "",
    title: "",
    company: "",
    email: "",
    phone: "",
    website: "",
    accent_color: "#4f46e5",
  });
  const [resumeDraft, setResumeDraft] = useState<ResumeDraft>({
    name: "",
    headline: "",
    email: "",
    phone: "",
    location: "",
    website: "",
    summary: "",
    experience: "",
    education: "",
    skills: "",
    cover_letter: "",
  });
  const [resumeTemplate, setResumeTemplate] = useState<ResumeTemplate>("classic");
  const [resumeRewriteWithAi, setResumeRewriteWithAi] = useState(false);
  const isPdfOrganizer = tool?.slug === "organize-pdf";
  const isESign = tool?.slug === "esign-pdf";
  const isPdfEdit = tool?.slug === "edit-pdf";
  const isVideoTrimmer = tool?.slug === "video-trimmer";
  const isInvoiceGenerator = tool?.slug === "invoice-generator";
  const isBusinessCard = tool?.slug === "business-card";
  const isResumeBuilder = tool?.slug === "resume-builder";

  useEffect(() => {
    if (!isInvoiceGenerator) return;
    let live = true;
    void Promise.all([
      fetch("/api/business/invoice/clients", {
        credentials: "include",
        cache: "no-store",
      }),
      fetch("/api/business/invoice/items", {
        credentials: "include",
        cache: "no-store",
      }),
      fetch("/api/business/invoice/recurring", {
        credentials: "include",
        cache: "no-store",
      }),
    ])
      .then(async ([clientsResponse, itemsResponse, recurringResponse]) => {
        if (!clientsResponse.ok || !itemsResponse.ok || !recurringResponse.ok)
          return;
        const [clients, items, recurring] = await Promise.all([
          clientsResponse.json() as Promise<SavedClient[]>,
          itemsResponse.json() as Promise<SavedInvoiceItem[]>,
          recurringResponse.json() as Promise<RecurringInvoice[]>,
        ]);
        if (live) {
          setSavedClients(clients);
          setSavedInvoiceItems(items);
          setRecurringInvoices(recurring);
        }
      })
      .catch(() => {
        if (live)
          setInvoiceSaveMessage("Saved clients and items could not be loaded.");
      });
    return () => {
      live = false;
    };
  }, [isInvoiceGenerator]);

  async function saveInvoiceRecord(path: "clients" | "items", payload: object) {
    const token = await csrfToken();
    const response = await fetch(`/api/business/invoice/${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      if (response.status === 401)
        throw new Error("Sign in to save clients and items.");
      const data = (await response.json().catch(() => ({}))) as {
        detail?: string;
      };
      throw new Error(data.detail || "Could not save this record.");
    }
    return response.json() as Promise<SavedClient | SavedInvoiceItem>;
  }

  async function createRecurringSchedule(interval: "weekly" | "monthly") {
    const token = await csrfToken();
    const response = await fetch("/api/business/invoice/recurring", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
      body: JSON.stringify({
        interval,
        invoice: {
          ...invoiceDraft,
          issued_on:
            invoiceDraft.issued_on || new Date().toISOString().slice(0, 10),
          due_on: invoiceDraft.due_on || null,
          business_email: invoiceDraft.business_email || null,
          client_email: invoiceDraft.client_email || null,
          items: invoiceItems,
        },
      }),
    });
    if (!response.ok) {
      if (response.status === 401)
        throw new Error("Sign in to schedule recurring invoices.");
      if (response.status === 402)
        throw new Error("Recurring invoices require Pro.");
      const data = (await response.json().catch(() => ({}))) as {
        detail?: string;
      };
      throw new Error(data.detail || "Could not schedule this invoice.");
    }
    const schedule = (await response.json()) as RecurringInvoice;
    setRecurringInvoices((current) => [schedule, ...current]);
  }

  async function changeRecurringSchedule(
    schedule: RecurringInvoice,
    active?: boolean,
  ) {
    const token = await csrfToken();
    const response = await fetch(
      `/api/business/invoice/recurring/${schedule.id}`,
      {
        method: active === undefined ? "DELETE" : "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
        ...(active === undefined ? {} : { body: JSON.stringify({ active }) }),
      },
    );
    if (!response.ok)
      throw new Error("Could not update this recurring invoice.");
    setRecurringInvoices((current) =>
      active === undefined
        ? current.filter((item) => item.id !== schedule.id)
        : current.map((item) =>
            item.id === schedule.id ? { ...item, active } : item,
          ),
    );
  }
  const handlePdfOrderChange = useCallback((pageOrder: string) => {
    setOptionValues((current) => ({ ...current, page_order: pageOrder }));
  }, []);
  const handlePdfReadyChange = useCallback(
    (ready: boolean) => setPdfReady(ready),
    [],
  );
  const handleVideoTrimChange = useCallback(
    (startSeconds: number, endSeconds: number, ready: boolean) => {
      setOptionValues((current) => ({
        ...current,
        start_seconds: String(startSeconds),
        end_seconds: String(endSeconds),
      }));
      setVideoTrimReady(ready);
    },
    [],
  );

  useEffect(() => {
    setBatchMode(false);
    setEsignDraft(null);
    setPdfEditDraft(null);
    setVideoTrimReady(false);
    setInvoiceDraft({
      document_type: "invoice",
      number: "INV-001",
      currency: "CAD",
      issued_on: "",
      due_on: "",
      business_name: "",
      business_email: "",
      business_address: "",
      client_name: "",
      client_email: "",
      client_address: "",
      notes: "",
      tax_percent: "0",
    });
    setInvoiceItems([{ description: "", quantity: "1", unit_price: "0" }]);
    setBusinessCard({
      name: "",
      title: "",
      company: "",
      email: "",
      phone: "",
      website: "",
      accent_color: "#4f46e5",
    });
    setResumeDraft({
      name: "",
      headline: "",
      email: "",
      phone: "",
      location: "",
      website: "",
      summary: "",
      experience: "",
      education: "",
      skills: "",
      cover_letter: "",
    });
    setOptionValues(
      Object.fromEntries(
        Object.entries(tool?.options_schema?.properties ?? {}).map(
          ([key, property]) => [
            key,
            property.default == null ? "" : String(property.default),
          ],
        ),
      ),
    );
  }, [tool?.slug, tool?.options_schema]);

  function buildOptions(): Record<string, unknown> {
    const properties = tool?.options_schema?.properties ?? {};
    return Object.fromEntries(
      Object.entries(optionValues).map(([key, value]) => {
        const type = properties[key]?.type;
        if ((type === "integer" || type === "number") && value.trim())
          return [key, Number(value)];
        if (type === "boolean") return [key, value === "true"];
        return [key, value];
      }),
    );
  }

  useEffect(() => {
    void fetch("/api/security/config", { cache: "no-store" })
      .then(
        (response) =>
          response.json() as Promise<{ turnstile_site_key: string | null }>,
      )
      .then((config) => setTurnstileSiteKey(config.turnstile_site_key))
      .catch(() => setTurnstileSiteKey(null));
  }, []);

  useEffect(() => {
    if (!turnstileSiteKey) return;
    type TurnstileApi = {
      render: (
        element: HTMLElement,
        options: {
          sitekey: string;
          callback: (token: string) => void;
          "expired-callback": () => void;
        },
      ) => string;
      reset?: (id?: string) => void;
    };
    type TurnstileWindow = Window & { turnstile?: TurnstileApi };
    const widget = document.getElementById("rendercart-turnstile");
    if (!widget) return;
    let widgetId: string | undefined;
    let attempts = 0;
    const render = () => {
      const api = (window as TurnstileWindow).turnstile;
      if (!api) {
        attempts += 1;
        if (attempts < 20) window.setTimeout(render, 250);
        return;
      }
      widgetId = api.render(widget, {
        sitekey: turnstileSiteKey,
        callback: setTurnstileToken,
        "expired-callback": () => setTurnstileToken(""),
      });
    };
    const script = document.createElement("script");
    script.src =
      "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.nonce =
      document.querySelector<HTMLScriptElement>("script[nonce]")?.nonce ?? "";
    script.async = true;
    script.defer = true;
    script.onload = render;
    document.head.appendChild(script);
    return () => {
      const api = (window as TurnstileWindow).turnstile as
        (TurnstileApi & { remove?: (id: string) => void }) | undefined;
      if (widgetId) api?.remove?.(widgetId);
      script.remove();
    };
  }, [turnstileSiteKey]);

  useEffect(() => {
    if (!jobId) return;
    let live = true;
    const poll = async () => {
      const response = await fetch(`/api/jobs/${jobId}`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!response.ok) {
        if (live) setMessage("This job could not be found.");
        return;
      }
      const result = (await response.json()) as JobInfo;
      if (live) setJob(result);
      if (live && !["succeeded", "failed", "cancelled"].includes(result.state))
        window.setTimeout(poll, 1200);
    };
    void poll();
    return () => {
      live = false;
    };
  }, [jobId]);

  async function submit() {
    if (!tool) return;
    const hasInlineSource =
      isInvoiceGenerator ||
      isBusinessCard ||
      isResumeBuilder ||
      Object.values(buildOptions()).some(
        (value) => typeof value === "string" && value.trim().length > 0,
      );
    const summaryText = optionValues.source_text?.trim() ?? "";
    const summaryUrl = optionValues.source_url?.trim() ?? "";
    const summarySourceCount =
      Number(Boolean(summaryText)) +
      Number(Boolean(summaryUrl)) +
      Number(files.length > 0);
    if (tool.slug === "summarizer" && summarySourceCount !== 1) {
      setMessage(
        "Choose exactly one source: pasted text, a public URL, or one uploaded file.",
      );
      return;
    }
    if (["paraphraser", "grammar-fixer"].includes(tool.slug)) {
      const inlineText = optionValues.source_text?.trim() ?? "";
      if (Number(Boolean(inlineText)) + Number(files.length > 0) !== 1) {
        setMessage("Paste text or upload one text file.");
        return;
      }
    }
    if (tool.slug === "writing-helper" && !optionValues.prompt?.trim()) {
      setMessage("Describe what you want the writing helper to draft.");
      return;
    }
    if (
      isInvoiceGenerator &&
      (!invoiceDraft.number.trim() ||
        !invoiceDraft.business_name.trim() ||
        !invoiceDraft.client_name.trim() ||
        invoiceItems.some(
          (item) =>
            !item.description.trim() ||
            Number(item.quantity) <= 0 ||
            Number(item.unit_price) < 0,
        ))
    ) {
      setMessage(
        "Add an invoice number, both business names, and valid line items.",
      );
      return;
    }
    if (isBusinessCard && !businessCard.name.trim()) {
      setMessage("Enter the name to print on the business card.");
      return;
    }
    if (
      isResumeBuilder &&
      (!resumeDraft.name.trim() ||
        ![
          resumeDraft.summary,
          resumeDraft.experience,
          resumeDraft.education,
          resumeDraft.skills,
        ].some((value) => value.trim()))
    ) {
      setMessage("Add your name and at least one resume section.");
      return;
    }
    if (!files.length && tool.inputs?.min_files === 0 && !hasInlineSource) {
      setMessage("Paste text, enter a URL, or choose a file first.");
      return;
    }
    if (
      batchMode &&
      (files.length < 2 || files.length > (tool.batch_max_files ?? 20))
    ) {
      setMessage(`Batch mode needs 2–${tool.batch_max_files ?? 20} files.`);
      return;
    }
    if (
      tool.batchable &&
      files.length > 1 &&
      !batchMode &&
      !["merge-pdf", "image-to-pdf"].includes(tool.slug)
    ) {
      setMessage("Choose Batch mode to process these files separately.");
      return;
    }
    setBusy(true);
    setMessage("");
    setPaywall(false);
    trackRenderCartEvent("tool-job-submit", { tool: tool.slug });
    try {
      const token = await csrfToken();
      const uploadIds: string[] = [];
      let filesToUpload = files;
      let options = buildOptions();
      if (isInvoiceGenerator) {
        options = {
          ...options,
          invoice_json: JSON.stringify({
            ...invoiceDraft,
            issued_on:
              invoiceDraft.issued_on || new Date().toISOString().slice(0, 10),
            due_on: invoiceDraft.due_on || null,
            business_email: invoiceDraft.business_email || null,
            client_email: invoiceDraft.client_email || null,
            tax_percent: invoiceDraft.tax_percent || "0",
            items: invoiceItems,
          }),
        };
      }
      if (isBusinessCard) {
        options = {
          ...options,
          card_json: JSON.stringify({ ...businessCard, layout: "classic" }),
        };
      }
      if (isResumeBuilder) {
        options = {
          ...options,
          template: resumeTemplate,
          rewrite_with_ai: resumeRewriteWithAi,
          resume_json: JSON.stringify({
            ...resumeDraft,
            experience: resumeDraft.experience
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean),
            education: resumeDraft.education
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean),
            skills: resumeDraft.skills
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
          }),
        };
      }
      if (isPdfEdit) {
        const original = files[0];
        if (!original || !pdfEditDraft?.ready)
          throw new Error(
            "Choose a PDF and wait for the editor to finish loading.",
          );
        filesToUpload = [await createEditedPdf(original, pdfEditDraft)];
      }
      if (isESign) {
        const original = files[0];
        if (!original || !esignDraft?.ready)
          throw new Error(
            "Add your signature, signer details, and consent before continuing.",
          );
        const pdfLib = await import("pdf-lib");
        const pdf = await pdfLib.PDFDocument.load(await original.arrayBuffer());
        const page = pdf.getPage(esignDraft.pageNumber - 1);
        const signatureBytes = Uint8Array.from(
          atob(esignDraft.signaturePng.split(",")[1]),
          (char) => char.charCodeAt(0),
        );
        const signature = await pdf.embedPng(signatureBytes);
        const { width, height } = page.getSize();
        const imageWidth = width * 0.42;
        const imageHeight = Math.min(
          height * 0.15,
          (imageWidth * signature.height) / signature.width,
        );
        page.drawImage(signature, {
          x: width * 0.08,
          y: height * 0.08,
          width: imageWidth,
          height: imageHeight,
        });
        const signedBytes = await pdf.save();
        const stem = original.name.replace(/\.pdf$/i, "") || "document";
        filesToUpload = [
          original,
          new File([new Uint8Array(signedBytes)], `${stem}-signed.pdf`, {
            type: "application/pdf",
          }),
        ];
        options = {
          ...options,
          signer_name: esignDraft.signerName,
          signer_email: esignDraft.signerEmail,
          page_number: esignDraft.pageNumber,
          consented: esignDraft.consented,
        };
      }
      for (const file of filesToUpload) {
        const contentType = uploadContentType(tool.slug, file);
        const signedResponse = await fetch("/api/uploads/presign", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
          body: JSON.stringify({
            tool_slug: tool.slug,
            filename: file.name,
            content_type: contentType,
            size_bytes: file.size,
          }),
        });
        const signed = (await signedResponse.json()) as {
          upload_id?: string;
          upload_url?: string;
          headers?: Record<string, string>;
          detail?: string;
        };
        if (!signedResponse.ok || !signed.upload_id || !signed.upload_url)
          throw new Error(signed.detail ?? "Could not prepare file upload.");
        const uploaded = await fetch(signed.upload_url, {
          method: "PUT",
          headers: signed.headers,
          body: file,
        });
        if (!uploaded.ok) throw new Error("File upload failed. Please retry.");
        uploadIds.push(signed.upload_id);
      }
      setUploadedIds(uploadIds);
      const created = await fetch(`/api/tools/${tool.slug}/jobs`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
        body: JSON.stringify({
          upload_ids: uploadIds,
          options,
          batch_mode: batchMode,
          turnstile_token: turnstileToken || null,
        }),
      });
      const payload = (await created.json()) as JobInfo & { detail?: string };
      if (!created.ok) {
        if (created.status === 402) {
          setPaywall(true);
          trackRenderCartEvent("paywall-shown", { tool: tool.slug });
        }
        throw new Error(payload.detail ?? "Could not create job.");
      }
      window.location.assign(`/jobs/${payload.job_id}`);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Something went wrong.",
      );
      if (turnstileToken) {
        type TurnstileWindow = Window & { turnstile?: { reset?: () => void } };
        (window as TurnstileWindow).turnstile?.reset?.();
        setTurnstileToken("");
      }
      setBusy(false);
    }
  }

  async function purchaseSingleJob(product: "job_s" | "job_m" | "job_l") {
    const hasInlineSource = Object.values(buildOptions()).some(
      (value) => typeof value === "string" && value.trim().length > 0,
    );
    if (!tool || (uploadedIds.length === 0 && !hasInlineSource)) {
      setMessage("Add your text or URL, or upload a file, before checkout.");
      return;
    }
    setBusy(true);
    setMessage("");
    trackRenderCartEvent("paywall-checkout-click", { tool: tool?.slug ?? "unknown", product });
    try {
      const token = await csrfToken();
      const options = buildOptions();
      if (isESign && esignDraft) {
        options.signer_name = esignDraft.signerName;
        options.signer_email = esignDraft.signerEmail;
        options.page_number = esignDraft.pageNumber;
        options.consented = esignDraft.consented;
      }
      const created = await fetch(`/api/tools/${tool.slug}/jobs`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
        body: JSON.stringify({
          upload_ids: uploadedIds,
          options,
          batch_mode: false,
          turnstile_token: turnstileToken || null,
          paid_tier: product,
        }),
      });
      const job = (await created.json()) as {
        job_id?: string;
        detail?: string;
      };
      if (!created.ok || !job.job_id) {
        throw new Error(job.detail ?? "Could not prepare the paid job.");
      }
      const checkout = await fetch(`/api/billing/jobs/${job.job_id}/checkout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
        body: JSON.stringify({ product }),
      });
      const payment = (await checkout.json()) as {
        url?: string;
        detail?: string;
      };
      if (!checkout.ok || !payment.url) {
        throw new Error(
          payment.detail ?? "Could not start single-job checkout.",
        );
      }
      window.location.assign(payment.url);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not start single-job checkout.",
      );
      setBusy(false);
    }
  }

  async function purchasePreviewUnlock() {
    if (!job?.payment_product) return;
    setBusy(true);
    setMessage("");
    try {
      const token = await csrfToken();
      const response = await fetch(`/api/billing/jobs/${job.job_id}/checkout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-RC-CSRF": token },
        body: JSON.stringify({ product: job.payment_product }),
      });
      const payment = (await response.json()) as {
        url?: string;
        detail?: string;
      };
      if (!response.ok || !payment.url) {
        throw new Error(payment.detail ?? "Could not start checkout.");
      }
      window.location.assign(payment.url);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Could not start checkout.",
      );
      setBusy(false);
    }
  }

  if (jobId) {
    return (
      <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
        <p className="font-medium">
          {job
            ? job.state[0].toUpperCase() + job.state.slice(1)
            : "Loading job…"}
        </p>
        {job && (
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
            <div
              className="h-full bg-violet-600 transition-all"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        )}
        {job?.download_url && (
          <a
            className="mt-5 inline-flex rounded-xl bg-violet-600 px-5 py-3 font-semibold text-white"
            href={job.download_url}
          >
            Download result
          </a>
        )}
        {job?.tool_slug === "chat-with-pdf" && job.state === "succeeded" && (
          <PdfChatPanel jobId={job.job_id} />
        )}
        {job?.locked_preview && (
          <div className="mt-5 rounded-xl bg-violet-50 p-4 dark:bg-violet-950">
            <p className="font-semibold">Your full result is ready</p>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              {job.tool_slug === "edit-pdf"
                ? "The free PDF is watermarked. Unlock a clean edited PDF with a one-time payment."
                : "The preview is free. Unlock the original-resolution PNG with a one-time payment."}
            </p>
            {job.can_unlock && (
              <button
                disabled={busy}
                onClick={() => void purchasePreviewUnlock()}
                className="mt-3 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                Unlock full resolution · one-time payment
              </button>
            )}
            {!job.can_unlock && (
              <Link
                className="mt-3 inline-block text-sm font-semibold text-violet-700 dark:text-violet-300"
                href={`/login?next=/jobs/${job.job_id}`}
              >
                Sign in to unlock
              </Link>
            )}
          </div>
        )}
        {job?.error_code === "insufficient_credits" ? (
          <p className="mt-4 text-sm text-red-600">
            This job needs more credits.{" "}
            <Link className="font-semibold underline" href="/account/billing">
              Open billing to buy a credit pack.
            </Link>
          </p>
        ) : job?.error_code === "document_page_limit_exceeded" ? (
          <p className="mt-4 text-sm text-red-600">
            Free translation is limited to one page.{" "}
            <Link className="font-semibold underline" href="/pricing">
              Choose Pro or a day pass to translate the full document.
            </Link>
          </p>
        ) : (
          job?.error_code && (
            <p className="mt-4 text-sm text-red-600">
              The job failed ({job.error_code}). Please try again.
            </p>
          )
        )}
        {message && <p className="mt-4 text-sm text-red-600">{message}</p>}
      </div>
    );
  }

  if (!tool?.inputs) return null;
  const paidTier = tool.job_tier ?? "S";
  const paidProduct = `job_${paidTier.toLowerCase()}` as
    "job_s" | "job_m" | "job_l";
  const configuredPrice = tool.prices?.[paidProduct] ?? tool.single_job_price_cents;
  const paidPrice =
    typeof configuredPrice === "number"
      ? `$${(configuredPrice / 100).toFixed(2)}`
      : paidTier === "S"
        ? "$0.99"
        : paidTier === "M"
          ? "$1.99"
          : "$2.99";
  const allowsMultiFileSingleJob = [
    "merge-pdf",
    "image-to-pdf",
    "esign-pdf",
    "video-merger",
  ].includes(tool.slug);
  const minimumFiles = isESign ? 1 : tool.inputs.min_files;
  const invoiceTotal = invoiceItems.reduce(
    (sum, item) =>
      sum + Number(item.quantity || 0) * Number(item.unit_price || 0),
    0,
  );
  return (
    <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
      {!isInvoiceGenerator && !isBusinessCard && !isResumeBuilder && (
        <label className="block text-sm font-semibold">
          {tool.inputs.min_files === 0
            ? "Choose a file (optional when text or URL is provided)"
            : "Choose files"}
          <input
            className="mt-3 block w-full rounded-xl border border-slate-300 p-3 text-sm dark:border-slate-600"
            type="file"
            multiple={
              !isESign &&
              !isPdfEdit &&
              (tool.batchable ||
                tool.slug === "merge-pdf" ||
                tool.slug === "image-to-pdf" ||
                tool.slug === "video-merger")
            }
            accept={tool.inputs.accept.join(",")}
            onChange={(event) => {
              setFiles(Array.from(event.target.files ?? []));
              setUploadedIds([]);
              setEsignDraft(null);
              setPdfEditDraft(null);
              setVideoTrimReady(false);
            }}
          />
        </label>
      )}
      {isInvoiceGenerator && (
        <div className="mt-4 space-y-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="text-sm font-semibold">
              Document type
              <select
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                value={invoiceDraft.document_type}
                onChange={(event) =>
                  setInvoiceDraft((current) => ({
                    ...current,
                    document_type: event.target
                      .value as InvoiceDraft["document_type"],
                  }))
                }
              >
                <option value="invoice">Invoice</option>
                <option value="quote">Quote</option>
                <option value="receipt">Receipt</option>
              </select>
            </label>
            <label className="text-sm font-semibold">
              <span className="flex items-center justify-between gap-2">
                Number
                <button
                  type="button"
                  className="text-xs font-semibold text-violet-700"
                  onClick={() => {
                    void (async () => {
                      try {
                        const token = await csrfToken();
                        const response = await fetch(
                          "/api/business/invoice/number",
                          {
                            method: "POST",
                            credentials: "include",
                            headers: {
                              "Content-Type": "application/json",
                              "X-RC-CSRF": token,
                            },
                            body: JSON.stringify({
                              document_type: invoiceDraft.document_type,
                            }),
                          },
                        );
                        if (!response.ok)
                          throw new Error(
                            response.status === 401
                              ? "Sign in to use sequential numbers."
                              : "Could not reserve a number.",
                          );
                        const data = (await response.json()) as {
                          number: string;
                        };
                        setInvoiceDraft((current) => ({
                          ...current,
                          number: data.number,
                        }));
                        setInvoiceSaveMessage("Sequential number reserved.");
                      } catch (error) {
                        setInvoiceSaveMessage(
                          error instanceof Error
                            ? error.message
                            : "Could not reserve a number.",
                        );
                      }
                    })();
                  }}
                >
                  Use next number
                </button>
              </span>
              <input
                required
                maxLength={40}
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                value={invoiceDraft.number}
                onChange={(event) =>
                  setInvoiceDraft((current) => ({
                    ...current,
                    number: event.target.value,
                  }))
                }
              />
            </label>
            <label className="text-sm font-semibold">
              Currency
              <select
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                value={invoiceDraft.currency}
                onChange={(event) =>
                  setInvoiceDraft((current) => ({
                    ...current,
                    currency: event.target.value,
                  }))
                }
              >
                {[
                  "CAD",
                  "USD",
                  "EUR",
                  "GBP",
                  "AUD",
                  "NZD",
                  "JPY",
                  "CHF",
                  "INR",
                ].map((currency) => (
                  <option key={currency}>{currency}</option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold">
              Issue date
              <input
                type="date"
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                value={invoiceDraft.issued_on}
                onChange={(event) =>
                  setInvoiceDraft((current) => ({
                    ...current,
                    issued_on: event.target.value,
                  }))
                }
              />
            </label>
            <label className="text-sm font-semibold">
              Due date
              <input
                type="date"
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                value={invoiceDraft.due_on}
                onChange={(event) =>
                  setInvoiceDraft((current) => ({
                    ...current,
                    due_on: event.target.value,
                  }))
                }
              />
            </label>
            <label className="text-sm font-semibold">
              Tax %
              <input
                type="number"
                min="0"
                max="100"
                step="0.01"
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                value={invoiceDraft.tax_percent}
                onChange={(event) =>
                  setInvoiceDraft((current) => ({
                    ...current,
                    tax_percent: event.target.value,
                  }))
                }
              />
            </label>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <fieldset className="space-y-3">
              <legend className="font-semibold">Your business</legend>
              {(
                ["business_name", "business_email", "business_address"] as const
              ).map((key) => (
                <label key={key} className="block text-sm font-medium">
                  {key === "business_name"
                    ? "Business name"
                    : key === "business_email"
                      ? "Email"
                      : "Address"}
                  {key === "business_address" ? (
                    <textarea
                      className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent p-3 font-normal dark:border-slate-600"
                      value={invoiceDraft[key]}
                      onChange={(event) =>
                        setInvoiceDraft((current) => ({
                          ...current,
                          [key]: event.target.value,
                        }))
                      }
                    />
                  ) : (
                    <input
                      type={key === "business_email" ? "email" : "text"}
                      required={key === "business_name"}
                      className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                      value={invoiceDraft[key]}
                      onChange={(event) =>
                        setInvoiceDraft((current) => ({
                          ...current,
                          [key]: event.target.value,
                        }))
                      }
                    />
                  )}
                </label>
              ))}
            </fieldset>
            <fieldset className="space-y-3">
              <legend className="font-semibold">Customer</legend>
              {savedClients.length > 0 && (
                <label className="block text-sm font-medium">
                  Use saved customer
                  <select
                    className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
                    defaultValue=""
                    onChange={(event) => {
                      const selected = savedClients.find(
                        (client) => client.id === event.target.value,
                      );
                      if (selected)
                        setInvoiceDraft((current) => ({
                          ...current,
                          client_name: selected.name,
                          client_email: selected.email,
                          client_address: selected.address,
                        }));
                    }}
                  >
                    <option value="">Choose a saved customer</option>
                    {savedClients.map((client) => (
                      <option key={client.id} value={client.id}>
                        {client.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {(["client_name", "client_email", "client_address"] as const).map(
                (key) => (
                  <label key={key} className="block text-sm font-medium">
                    {key === "client_name"
                      ? "Customer name"
                      : key === "client_email"
                        ? "Email"
                        : "Address"}
                    {key === "client_address" ? (
                      <textarea
                        className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent p-3 font-normal dark:border-slate-600"
                        value={invoiceDraft[key]}
                        onChange={(event) =>
                          setInvoiceDraft((current) => ({
                            ...current,
                            [key]: event.target.value,
                          }))
                        }
                      />
                    ) : (
                      <input
                        type={key === "client_email" ? "email" : "text"}
                        required={key === "client_name"}
                        className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                        value={invoiceDraft[key]}
                        onChange={(event) =>
                          setInvoiceDraft((current) => ({
                            ...current,
                            [key]: event.target.value,
                          }))
                        }
                      />
                    )}
                  </label>
                ),
              )}
              <button
                type="button"
                className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold dark:border-slate-600"
                onClick={() => {
                  setInvoiceSaveMessage("");
                  void saveInvoiceRecord("clients", {
                    name: invoiceDraft.client_name,
                    email: invoiceDraft.client_email,
                    address: invoiceDraft.client_address,
                  })
                    .then((record) => {
                      setSavedClients((current) => [
                        record as SavedClient,
                        ...current,
                      ]);
                      setInvoiceSaveMessage("Customer saved to your account.");
                    })
                    .catch((error: unknown) =>
                      setInvoiceSaveMessage(
                        error instanceof Error
                          ? error.message
                          : "Could not save customer.",
                      ),
                    );
                }}
              >
                Save customer
              </button>
            </fieldset>
          </div>
          <div>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">Line items</h3>
              {savedInvoiceItems.length > 0 && (
                <select
                  aria-label="Add a saved item"
                  className="rounded-lg border border-slate-300 bg-transparent px-2 py-2 text-xs dark:border-slate-600"
                  defaultValue=""
                  onChange={(event) => {
                    const selected = savedInvoiceItems.find(
                      (item) => item.id === event.target.value,
                    );
                    if (selected)
                      setInvoiceItems((items) => [
                        ...items,
                        {
                          description: selected.description,
                          quantity: "1",
                          unit_price: selected.unit_price,
                        },
                      ]);
                    event.target.value = "";
                  }}
                >
                  <option value="">Add saved item…</option>
                  {savedInvoiceItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.description}
                    </option>
                  ))}
                </select>
              )}
              <button
                type="button"
                className="text-sm font-semibold text-violet-700"
                onClick={() =>
                  setInvoiceItems((items) => [
                    ...items,
                    { description: "", quantity: "1", unit_price: "0" },
                  ])
                }
              >
                Add item
              </button>
            </div>
            <div className="mt-3 space-y-3">
              {invoiceItems.map((item, index) => (
                <div
                  key={index}
                  className="grid gap-3 rounded-xl bg-slate-50 p-3 sm:grid-cols-[1fr_100px_140px_auto] dark:bg-slate-800"
                >
                  <label className="text-xs font-semibold">
                    Description
                    <input
                      className="mt-1 block w-full rounded-lg border border-slate-300 bg-transparent px-2 py-2 text-sm font-normal dark:border-slate-600"
                      value={item.description}
                      onChange={(event) =>
                        setInvoiceItems((items) =>
                          items.map((current, row) =>
                            row === index
                              ? { ...current, description: event.target.value }
                              : current,
                          ),
                        )
                      }
                    />
                  </label>
                  <label className="text-xs font-semibold">
                    Quantity
                    <input
                      type="number"
                      min="0.001"
                      step="0.001"
                      className="mt-1 block w-full rounded-lg border border-slate-300 bg-transparent px-2 py-2 text-sm font-normal dark:border-slate-600"
                      value={item.quantity}
                      onChange={(event) =>
                        setInvoiceItems((items) =>
                          items.map((current, row) =>
                            row === index
                              ? { ...current, quantity: event.target.value }
                              : current,
                          ),
                        )
                      }
                    />
                  </label>
                  <label className="text-xs font-semibold">
                    Unit price
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      className="mt-1 block w-full rounded-lg border border-slate-300 bg-transparent px-2 py-2 text-sm font-normal dark:border-slate-600"
                      value={item.unit_price}
                      onChange={(event) =>
                        setInvoiceItems((items) =>
                          items.map((current, row) =>
                            row === index
                              ? { ...current, unit_price: event.target.value }
                              : current,
                          ),
                        )
                      }
                    />
                  </label>
                  <button
                    type="button"
                    aria-label="Remove line item"
                    disabled={invoiceItems.length === 1}
                    className="self-end rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-40"
                    onClick={() =>
                      setInvoiceItems((items) =>
                        items.filter((_current, row) => row !== index),
                      )
                    }
                  >
                    Remove
                  </button>
                  <button
                    type="button"
                    className="text-left text-xs font-semibold text-violet-700 sm:col-span-4"
                    onClick={() => {
                      setInvoiceSaveMessage("");
                      void saveInvoiceRecord("items", {
                        description: item.description,
                        unit_price: item.unit_price,
                      })
                        .then((record) => {
                          setSavedInvoiceItems((current) => [
                            record as SavedInvoiceItem,
                            ...current,
                          ]);
                          setInvoiceSaveMessage(
                            "Line item saved to your account.",
                          );
                        })
                        .catch((error: unknown) =>
                          setInvoiceSaveMessage(
                            error instanceof Error
                              ? error.message
                              : "Could not save line item.",
                          ),
                        );
                    }}
                  >
                    Save item
                  </button>
                </div>
              ))}
            </div>
            <p className="mt-3 text-right text-sm font-semibold">
              Subtotal: {invoiceDraft.currency} {invoiceTotal.toFixed(2)}
            </p>
          </div>
          <label className="block text-sm font-semibold">
            Notes
            <textarea
              maxLength={2000}
              className="mt-2 block min-h-20 w-full rounded-xl border border-slate-300 bg-transparent p-3 font-normal dark:border-slate-600"
              value={invoiceDraft.notes}
              onChange={(event) =>
                setInvoiceDraft((current) => ({
                  ...current,
                  notes: event.target.value,
                }))
              }
            />
          </label>
          <p className="text-xs text-slate-500">
            Free PDFs include “Made with RenderCart”. Pro and day-pass users
            receive an unbranded PDF. Tax and totals are calculated from the
            values you enter.
          </p>
          <section className="space-y-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
            <div>
              <h3 className="font-semibold">Recurring invoices · Pro</h3>
              <p className="mt-1 text-xs text-slate-500">
                Schedule this invoice to generate again. Each run gets a fresh
                date and sequential number, then appears in your job history.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {(["weekly", "monthly"] as const).map((interval) => (
                <button
                  key={interval}
                  type="button"
                  disabled={invoiceDraft.document_type !== "invoice"}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold disabled:opacity-40 dark:border-slate-600"
                  onClick={() => {
                    setInvoiceSaveMessage("");
                    void createRecurringSchedule(interval)
                      .then(() =>
                        setInvoiceSaveMessage(`${interval} schedule created.`),
                      )
                      .catch((error: unknown) =>
                        setInvoiceSaveMessage(
                          error instanceof Error
                            ? error.message
                            : "Could not schedule invoice.",
                        ),
                      );
                  }}
                >
                  Repeat {interval}
                </button>
              ))}
            </div>
            {recurringInvoices.map((schedule) => (
              <div
                key={schedule.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800"
              >
                <span>
                  {schedule.interval} · {schedule.active ? "Active" : "Paused"}{" "}
                  · next {new Date(schedule.next_run_at).toLocaleDateString()}
                </span>
                <div className="flex gap-3">
                  <button
                    type="button"
                    className="font-semibold text-violet-700"
                    onClick={() =>
                      void changeRecurringSchedule(
                        schedule,
                        !schedule.active,
                      ).catch((error: unknown) =>
                        setInvoiceSaveMessage(
                          error instanceof Error
                            ? error.message
                            : "Could not update schedule.",
                        ),
                      )
                    }
                  >
                    {schedule.active ? "Pause" : "Resume"}
                  </button>
                  <button
                    type="button"
                    className="font-semibold text-red-700"
                    onClick={() =>
                      void changeRecurringSchedule(schedule).catch(
                        (error: unknown) =>
                          setInvoiceSaveMessage(
                            error instanceof Error
                              ? error.message
                              : "Could not delete schedule.",
                          ),
                      )
                    }
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </section>
          {invoiceSaveMessage && (
            <p
              aria-live="polite"
              className="text-sm text-slate-600 dark:text-slate-300"
            >
              {invoiceSaveMessage}
            </p>
          )}
        </div>
      )}
      {isBusinessCard && (
        <div className="mt-4 space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            {(
              [
                ["name", "Name", true],
                ["title", "Job title", false],
                ["company", "Company", false],
                ["email", "Email", false],
                ["phone", "Phone", false],
                ["website", "Website", false],
              ] as const
            ).map(([key, label, required]) => (
              <label key={key} className="text-sm font-semibold">
                {label}
                <input
                  required={required}
                  maxLength={
                    key === "email" ? 320 : key === "website" ? 240 : 120
                  }
                  type={key === "email" ? "email" : "text"}
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                  value={businessCard[key]}
                  onChange={(event) =>
                    setBusinessCard((current) => ({
                      ...current,
                      [key]: event.target.value,
                    }))
                  }
                />
              </label>
            ))}
            <label className="text-sm font-semibold">
              Accent color
              <input
                type="color"
                className="mt-2 block h-10 w-full rounded-xl border border-slate-300 bg-transparent p-1 dark:border-slate-600"
                value={businessCard.accent_color}
                onChange={(event) =>
                  setBusinessCard((current) => ({
                    ...current,
                    accent_color: event.target.value,
                  }))
                }
              />
            </label>
          </div>
          <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Preview
            </p>
            <div className="mt-3 aspect-[7/4] max-w-md rounded-lg bg-white p-5 text-slate-900 shadow-sm ring-1 ring-slate-200">
              <div
                className="h-full border-l-4 pl-4"
                style={{ borderColor: businessCard.accent_color }}
              >
                <p className="text-lg font-bold">
                  {businessCard.name || "Your name"}
                </p>
                <p className="text-sm text-slate-600">
                  {[businessCard.title, businessCard.company]
                    .filter(Boolean)
                    .join(" · ") || "Job title · Company"}
                </p>
                <div className="mt-5 space-y-1 text-xs text-slate-700">
                  {[
                    businessCard.email,
                    businessCard.phone,
                    businessCard.website,
                  ]
                    .filter(Boolean)
                    .map((value) => (
                      <p key={value}>{value}</p>
                    ))}
                </div>
              </div>
            </div>
          </div>
          <p className="text-xs text-slate-500">
            The PDF includes 0.125-inch bleed and trim marks around a 3.5 ×
            2-inch card. The file uses RGB colors; ask your printer whether they
            need a CMYK conversion. Free PDFs include “Made with RenderCart”.
          </p>
        </div>
      )}
      {isResumeBuilder && (
        <div className="mt-4 space-y-4">
          <label className="block text-sm font-semibold">
            PDF layout
            <select
              value={resumeTemplate}
              onChange={(event) =>
                setResumeTemplate(event.target.value as ResumeTemplate)
              }
              className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
            >
              <option value="classic">Classic — traditional blue headings</option>
              <option value="modern">Modern — teal accent and larger name</option>
              <option value="compact">Compact — tighter spacing for longer resumes</option>
            </select>
          </label>
          <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700">
            <input
              type="checkbox"
              checked={resumeRewriteWithAi}
              onChange={(event) => setResumeRewriteWithAi(event.target.checked)}
              className="mt-0.5 accent-violet-600"
            />
            <span>
              Rewrite summary, experience, and cover letter with AI (Pro, 2
              credits). Resume text may be sent to the configured AI provider;
              check the generated wording for accuracy before sharing.
            </span>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            {(
              [
                ["name", "Full name", true],
                ["headline", "Professional headline", false],
                ["email", "Email", false],
                ["phone", "Phone", false],
                ["location", "Location", false],
                ["website", "Website or LinkedIn", false],
              ] as const
            ).map(([key, label, required]) => (
              <label key={key} className="text-sm font-semibold">
                {label}
                <input
                  required={required}
                  maxLength={key === "email" ? 320 : 240}
                  type={key === "email" ? "email" : "text"}
                  className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                  value={resumeDraft[key]}
                  onChange={(event) =>
                    setResumeDraft((current) => ({
                      ...current,
                      [key]: event.target.value,
                    }))
                  }
                />
              </label>
            ))}
          </div>
          {(
            [
              [
                "summary",
                "Professional summary",
                "A short introduction and the role you are seeking.",
              ],
              [
                "experience",
                "Experience",
                "One job per line: title, company, dates, and accomplishments.",
              ],
              ["education", "Education", "One school or credential per line."],
              ["skills", "Skills", "Separate skills with commas."],
              [
                "cover_letter",
                "Cover letter (optional)",
                "Optional letter text will be added after the resume.",
              ],
            ] as const
          ).map(([key, label, placeholder]) => (
            <label key={key} className="block text-sm font-semibold">
              {label}
              <textarea
                maxLength={
                  key === "cover_letter"
                    ? 4000
                    : key === "summary"
                      ? 2000
                      : 6000
                }
                placeholder={placeholder}
                className="mt-2 block min-h-24 w-full rounded-xl border border-slate-300 bg-transparent p-3 font-normal dark:border-slate-600"
                value={resumeDraft[key]}
                onChange={(event) =>
                  setResumeDraft((current) => ({
                    ...current,
                    [key]: event.target.value,
                  }))
                }
              />
            </label>
          ))}
          <p className="text-xs text-slate-500">
            Creates a clean, single-column PDF. Free output includes the
            RenderCart footer. Review all details before sharing your resume.
          </p>
        </div>
      )}
      {tool.slug === "video-merger" && (
        <p className="mt-2 text-xs text-slate-500">
          Select 2–10 clips in the order you want them joined. Each clip must
          contain audio and video.
        </p>
      )}
      {tool.batchable && (
        <label className="mt-4 flex items-start gap-3 rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700">
          <input
            type="checkbox"
            checked={batchMode}
            onChange={(event) => setBatchMode(event.target.checked)}
            className="mt-0.5 accent-violet-600"
          />
          <span>
            <strong>Batch files (Pro)</strong>
            <span className="mt-1 block text-xs text-slate-500">
              Each file gets its own result in a ZIP. For Merge PDF, select
              files in pairs; each pair becomes one merged PDF. Batch accepts up
              to {tool.batch_max_files ?? 20} files.
            </span>
          </span>
        </label>
      )}
      {isPdfOrganizer ? (
        <PdfOrganizer
          file={files[0]}
          onOrderChange={handlePdfOrderChange}
          onReadyChange={handlePdfReadyChange}
        />
      ) : null}
      {isESign ? <PdfESign file={files[0]} onChange={setEsignDraft} /> : null}
      {isPdfEdit ? (
        <PdfEditor file={files[0]} onChange={setPdfEditDraft} />
      ) : null}
      {isVideoTrimmer ? (
        <VideoTrimmer file={files[0]} onChange={handleVideoTrimChange} />
      ) : null}
      {Object.entries(tool.options_schema?.properties ?? {})
        .filter(
          ([key]) =>
            (!isPdfOrganizer || key !== "page_order") &&
            (!isVideoTrimmer ||
              !["start_seconds", "end_seconds"].includes(key)),
        )
        .map(([key, property]) => (
          <label key={key} className="mt-5 block text-sm font-semibold">
            {property.title ?? key.replaceAll("_", " ")}
            {property.widget === "textarea" ? (
              <textarea
                className="mt-2 block min-h-40 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                minLength={property.minLength}
                maxLength={property.maxLength}
                value={optionValues[key] ?? ""}
                onChange={(event) =>
                  setOptionValues((current) => ({
                    ...current,
                    [key]: event.target.value,
                  }))
                }
              />
            ) : property.type === "boolean" ? (
              <input
                className="mt-2 block accent-violet-600"
                type="checkbox"
                checked={optionValues[key] === "true"}
                onChange={(event) =>
                  setOptionValues((current) => ({
                    ...current,
                    [key]: String(event.target.checked),
                  }))
                }
              />
            ) : property.enum ? (
              <select
                className="mt-2 block rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-600"
                value={optionValues[key] ?? ""}
                onChange={(event) =>
                  setOptionValues((current) => ({
                    ...current,
                    [key]: event.target.value,
                  }))
                }
              >
                {property.enum.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="mt-2 block w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 font-normal dark:border-slate-600"
                type={
                  property.format === "password"
                    ? "password"
                    : property.format === "uri"
                      ? "url"
                      : property.type === "integer" || property.type === "number"
                        ? "number"
                        : "text"
                }
                min={property.minimum}
                max={property.maximum}
                minLength={property.minLength}
                maxLength={property.maxLength}
                value={optionValues[key] ?? ""}
                onChange={(event) =>
                  setOptionValues((current) => ({
                    ...current,
                    [key]: event.target.value,
                  }))
                }
              />
            )}
            {property.description && (
              <span className="mt-1 block text-xs font-normal text-slate-500">
                {property.description}
              </span>
            )}
          </label>
        ))}
      {turnstileSiteKey && <div id="rendercart-turnstile" className="mt-5" />}
      {message && (
        <p role="alert" className="mt-4 text-sm text-red-600">
          {message}
        </p>
      )}
      {paywall && (
        <div className="mt-4 rounded-2xl bg-violet-50 p-4 dark:bg-violet-950">
          <p className="text-sm font-semibold">
            {batchMode ? "Batch processing requires Pro" : "Need this job now?"}
          </p>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            {batchMode
              ? "Switch to Pro to process multiple files in one job."
              : "Sign in and pay once to run this tool beyond the free limit."}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              disabled={
                busy ||
                (uploadedIds.length === 0 &&
                  !Object.values(optionValues).some((value) => value.trim())) ||
                batchMode ||
                (uploadedIds.length !== 1 &&
                  !allowsMultiFileSingleJob &&
                  uploadedIds.length > 0)
              }
              onClick={() => void purchaseSingleJob(paidProduct)}
              className="rounded-lg bg-violet-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              Single job · {paidPrice}
            </button>
          </div>
          <Link
            className="mt-3 inline-block text-sm font-semibold text-violet-700 dark:text-violet-300"
            href="/pricing"
            onClick={() => trackRenderCartEvent("paywall-pricing-click", { tool: tool?.slug ?? "unknown" })}
          >
            See plans and pricing →
          </Link>
        </div>
      )}
      <button
        disabled={
          busy ||
          files.length < minimumFiles ||
          (isPdfOrganizer && !pdfReady) ||
          (isESign && !esignDraft?.ready) ||
          (isPdfEdit && !pdfEditDraft?.ready) ||
          (isVideoTrimmer && !videoTrimReady) ||
          (!!turnstileSiteKey && !turnstileToken)
        }
        onClick={() => void submit()}
        className="mt-6 rounded-xl bg-violet-600 px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? "Uploading…" : "Run tool"}
      </button>
    </div>
  );
}
