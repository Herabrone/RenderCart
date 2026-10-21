"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import QRCode from "qrcode";
import { ClientImageTools } from "@/lib/client-image-tools";
import {
  convertCurrency,
  jsonToYaml,
  md5Hex,
  yamlToJson,
} from "@/lib/developer-tools";

type CurrencyRates = {
  base: "EUR";
  as_of: string;
  source: "ECB";
  rates: Record<string, number>;
  stale: boolean;
};

function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/gu,
    (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        character
      ] ?? character,
  );
}

function markdownToHtml(markdown: string): string {
  const blocks = markdown.split(/\n\s*\n/u).map((block) => {
    const lines = block.split("\n");
    const heading = /^(#{1,6})\s+(.+)$/u.exec(lines[0] ?? "");
    if (heading) {
      const level = heading[1].length;
      return `<h${level}>${inlineMarkdown(heading[2])}</h${level}>`;
    }
    if (lines.every((line) => /^\s*[-*+]\s+/u.test(line))) {
      return `<ul>${lines.map((line) => `<li>${inlineMarkdown(line.replace(/^\s*[-*+]\s+/u, ""))}</li>`).join("")}</ul>`;
    }
    if (lines.every((line) => /^\s*>/u.test(line))) {
      return `<blockquote>${lines.map((line) => inlineMarkdown(line.replace(/^\s*>\s?/u, ""))).join("<br>")}</blockquote>`;
    }
    return `<p>${lines.map(inlineMarkdown).join("<br>")}</p>`;
  });
  return blocks.join("\n");
}

function inlineMarkdown(value: string): string {
  return escapeHtml(value)
    .replace(/`([^`]+)`/gu, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/gu, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/gu, "<em>$1</em>")
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/giu,
      (_match, label: string, url: string) => {
        try {
          const parsed = new URL(url);
          if (parsed.protocol !== "https:" && parsed.protocol !== "http:")
            return label;
          return `<a href="${escapeHtml(parsed.href)}" rel="noopener noreferrer">${label}</a>`;
        } catch {
          return label;
        }
      },
    );
}

function htmlToMarkdown(value: string): string {
  const document = new DOMParser().parseFromString(value, "text/html");
  document
    .querySelectorAll("script,style,iframe,object,svg")
    .forEach((node) => node.remove());
  const convert = (node: Node): string => {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? "";
    if (!(node instanceof HTMLElement)) return "";
    const content = Array.from(node.childNodes, convert).join("");
    switch (node.tagName.toLowerCase()) {
      case "h1":
        return `# ${content.trim()}\n\n`;
      case "h2":
        return `## ${content.trim()}\n\n`;
      case "h3":
        return `### ${content.trim()}\n\n`;
      case "h4":
        return `#### ${content.trim()}\n\n`;
      case "h5":
        return `##### ${content.trim()}\n\n`;
      case "h6":
        return `###### ${content.trim()}\n\n`;
      case "p":
      case "div":
        return `${content.trim()}\n\n`;
      case "br":
        return "\n";
      case "strong":
      case "b":
        return `**${content}**`;
      case "em":
      case "i":
        return `*${content}*`;
      case "code":
        return `\`${content}\``;
      case "pre":
        return `\`\`\`\n${content.trim()}\n\`\`\`\n\n`;
      case "blockquote":
        return `${content
          .trim()
          .split("\n")
          .map((line) => `> ${line}`)
          .join("\n")}\n\n`;
      case "li":
        return `- ${content.trim()}\n`;
      case "a": {
        const href = node.getAttribute("href") ?? "";
        try {
          const parsed = new URL(href);
          return parsed.protocol === "https:" || parsed.protocol === "http:"
            ? `[${content}](${parsed.href})`
            : content;
        } catch {
          return content;
        }
      }
      default:
        return content;
    }
  };
  return Array.from(document.body.childNodes, convert)
    .join("")
    .replace(/\n{3,}/gu, "\n\n")
    .trim();
}

function parseCsv(value: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < value.length; index += 1) {
    const character = value[index];
    if (quoted) {
      if (character === '"' && value[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (character === '"') quoted = false;
      else field += character;
    } else if (character === '"' && field === "") quoted = true;
    else if (character === ",") {
      row.push(field);
      field = "";
    } else if (character === "\n") {
      row.push(field.replace(/\r$/u, ""));
      rows.push(row);
      row = [];
      field = "";
    } else field += character;
  }
  if (quoted) throw new Error("CSV contains an unclosed quote.");
  if (field || row.length) {
    row.push(field.replace(/\r$/u, ""));
    rows.push(row);
  }
  return rows;
}

async function testRegex(
  pattern: string,
  flags: string,
  text: string,
): Promise<string> {
  if (pattern.length > 200 || text.length > 4000)
    throw new Error(
      "Limit patterns to 200 characters and text to 4,000 characters.",
    );
  if (!/^[dgimsuvy]*$/u.test(flags))
    throw new Error("Use valid JavaScript regex flags.");
  const workerSource = `onmessage=({data})=>{try{const re=new RegExp(data.pattern,data.flags.includes('g')?data.flags:data.flags+'g');const matches=[...data.text.matchAll(re)].slice(0,100).map(m=>({match:m[0],index:m.index,groups:m.slice(1)}));postMessage({matches})}catch(e){postMessage({error:String(e)})}}`;
  const workerUrl = URL.createObjectURL(
    new Blob([workerSource], { type: "text/javascript" }),
  );
  const worker = new Worker(workerUrl);
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      worker.terminate();
      URL.revokeObjectURL(workerUrl);
      reject(new Error("Regex exceeded the 150 ms time limit."));
    }, 150);
    worker.onmessage = ({
      data,
    }: MessageEvent<{ matches?: unknown[]; error?: string }>) => {
      window.clearTimeout(timeout);
      worker.terminate();
      URL.revokeObjectURL(workerUrl);
      if (data.error) reject(new Error(data.error));
      else
        resolve(
          `${data.matches?.length ?? 0} match(es)\n${JSON.stringify(data.matches ?? [], null, 2)}`,
        );
    };
    worker.onerror = () => {
      window.clearTimeout(timeout);
      worker.terminate();
      URL.revokeObjectURL(workerUrl);
      reject(new Error("Regex worker failed."));
    };
    worker.postMessage({ pattern, flags, text });
  });
}

export function ClientToolRunner({ slug }: { slug: string }) {
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [error, setError] = useState("");
  const [qr, setQr] = useState("");
  const [length, setLength] = useState(20);
  const [action, setAction] = useState<"encode" | "decode">("encode");
  const [hashAlgorithm, setHashAlgorithm] = useState<
    "MD5" | "SHA-1" | "SHA-256"
  >("SHA-256");
  const [caseMode, setCaseMode] = useState<
    "lower" | "upper" | "title" | "sentence"
  >("lower");
  const [currencyRates, setCurrencyRates] = useState<CurrencyRates | null>(
    null,
  );
  const [currencyRatesError, setCurrencyRatesError] = useState("");
  const [sourceCurrency, setSourceCurrency] = useState("CAD");
  const [targetCurrency, setTargetCurrency] = useState("USD");
  const [busy, setBusy] = useState(false);
  const [barcodeReady, setBarcodeReady] = useState(false);
  const barcodeRef = useRef<SVGSVGElement>(null);
  const [signature, setSignature] = useState({
    name: "",
    title: "",
    company: "",
    email: "",
    phone: "",
    website: "",
  });

  useEffect(() => {
    if (slug !== "currency-converter") return;
    const controller = new AbortController();
    fetch("/api/currency-rates", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok)
          throw new Error("Daily reference rates are temporarily unavailable.");
        return (await response.json()) as CurrencyRates;
      })
      .then(setCurrencyRates)
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError")
          return;
        setCurrencyRatesError(
          cause instanceof Error
            ? cause.message
            : "Could not load currency rates.",
        );
      });
    return () => controller.abort();
  }, [slug]);

  function safeHtml(value: string): string {
    return value.replace(
      /[&<>"']/gu,
      (character) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[character] ?? character,
    );
  }

  const signatureHtml = `<table cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;color:#172033"><tr><td style="font-size:16px;font-weight:700">${safeHtml(signature.name || "Your Name")}</td></tr><tr><td style="padding-top:3px;font-size:13px;color:#475569">${safeHtml([signature.title, signature.company].filter(Boolean).join(" · ") || "Title · Company")}</td></tr><tr><td style="padding-top:8px;font-size:12px;color:#475569">${[signature.email, signature.phone, signature.website].filter(Boolean).map(safeHtml).join(" &nbsp;|&nbsp; ")}</td></tr></table>`;

  async function run() {
    setError("");
    setQr("");
    setBarcodeReady(false);
    try {
      if (slug === "json-formatter")
        setOutput(JSON.stringify(JSON.parse(input), null, 2));
      else if (slug === "markdown-html")
        setOutput(
          action === "encode" ? markdownToHtml(input) : htmlToMarkdown(input),
        );
      else if (slug === "json-csv") {
        if (input.length > 1_000_000)
          throw new Error("Limit input to one megabyte.");
        if (action === "encode") {
          const rows = JSON.parse(input) as unknown;
          if (
            !Array.isArray(rows) ||
            rows.some(
              (row) =>
                row === null || typeof row !== "object" || Array.isArray(row),
            )
          )
            throw new Error("JSON to CSV expects an array of objects.");
          const headers = [
            ...new Set(
              rows.flatMap((row) =>
                Object.keys(row as Record<string, unknown>),
              ),
            ),
          ];
          const escapeCsv = (value: unknown) => {
            const text =
              value === null || value === undefined
                ? ""
                : typeof value === "object"
                  ? JSON.stringify(value)
                  : String(value);
            return /[",\r\n]/u.test(text)
              ? `"${text.replace(/"/gu, '""')}"`
              : text;
          };
          setOutput(
            [
              headers.map(escapeCsv).join(","),
              ...rows.map((row) =>
                headers
                  .map((header) =>
                    escapeCsv((row as Record<string, unknown>)[header]),
                  )
                  .join(","),
              ),
            ].join("\n"),
          );
        } else {
          const [headers, ...rows] = parseCsv(input);
          if (!headers?.length) throw new Error("CSV needs a header row.");
          setOutput(
            JSON.stringify(
              rows
                .filter((row) => row.some(Boolean))
                .map((row) =>
                  Object.fromEntries(
                    headers.map((header, index) => [header, row[index] ?? ""]),
                  ),
                ),
              null,
              2,
            ),
          );
        }
      } else if (slug === "json-yaml") {
        setOutput(action === "encode" ? jsonToYaml(input) : yamlToJson(input));
      } else if (slug === "currency-converter") {
        const amount = Number(input.trim());
        if (!currencyRates)
          throw new Error("Daily reference rates are not available yet.");
        if (
          !Number.isFinite(amount) ||
          amount < 0 ||
          amount > 1_000_000_000_000
        )
          throw new Error("Enter an amount between 0 and 1,000,000,000,000.");
        const result = convertCurrency(
          amount,
          sourceCurrency,
          targetCurrency,
          currencyRates.rates,
        );
        setOutput(
          `${amount.toLocaleString()} ${sourceCurrency} = ${result.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })} ${targetCurrency}\n\nECB reference rate as of ${currencyRates.as_of}${currencyRates.stale ? " (cached; latest refresh unavailable)" : ""}. For information only, not for transaction pricing.`,
        );
      } else if (slug === "regex-tester") {
        const separator = input.indexOf("\n---\n");
        if (separator < 0)
          throw new Error(
            "Enter a pattern and flags on the first lines, then a line with --- and the sample text.",
          );
        const [patternLine = "", flagsLine = ""] = input
          .slice(0, separator)
          .split("\n");
        const slashPattern = /^\/(.*)\/([dgimsuvy]*)$/u.exec(
          patternLine.trim(),
        );
        const pattern = slashPattern?.[1] ?? patternLine;
        const flags = slashPattern?.[2] ?? flagsLine.trim();
        setOutput(await testRegex(pattern, flags, input.slice(separator + 5)));
      } else if (slug === "cron-builder") {
        const fields = input.trim().split(/\s+/u);
        const ranges: Array<[number, number]> = [
          [0, 59],
          [0, 23],
          [1, 31],
          [1, 12],
          [0, 7],
        ];
        const valid =
          fields.length === 5 &&
          fields.every((field, index) =>
            field.split(",").every((part) => {
              const [base, step, extra] = part.split("/");
              if (
                extra !== undefined ||
                (step !== undefined &&
                  (!/^\d+$/u.test(step) || Number(step) < 1))
              )
                return false;
              if (base === "*") return true;
              const range = /^(\d+)-(\d+)$/u.exec(base);
              const numbers = range
                ? [Number(range[1]), Number(range[2])]
                : /^\d+$/u.test(base)
                  ? [Number(base), Number(base)]
                  : [];
              return (
                numbers.length === 2 &&
                numbers[0] >= ranges[index][0] &&
                numbers[1] <= ranges[index][1] &&
                numbers[0] <= numbers[1]
              );
            }),
          );
        if (!valid)
          throw new Error(
            "Enter five valid cron fields: minute hour day-of-month month day-of-week.",
          );
        setOutput(
          `Valid five-field cron expression.\nMinute: ${fields[0]}\nHour: ${fields[1]}\nDay of month: ${fields[2]}\nMonth: ${fields[3]}\nDay of week: ${fields[4]}\nTimes are interpreted in the scheduler's configured time zone.`,
        );
      } else if (slug === "age-calculator") {
        const [birthValue, referenceValue] = input.split(/[\s,;]+/u);
        const birth = new Date(`${birthValue}T00:00:00Z`);
        const reference = referenceValue
          ? new Date(`${referenceValue}T00:00:00Z`)
          : new Date();
        if (
          !birthValue ||
          Number.isNaN(birth.valueOf()) ||
          Number.isNaN(reference.valueOf()) ||
          birth > reference
        )
          throw new Error(
            "Enter a birth date and optional reference date as YYYY-MM-DD.",
          );
        let years = reference.getUTCFullYear() - birth.getUTCFullYear();
        const birthdayThisYear = new Date(
          Date.UTC(
            reference.getUTCFullYear(),
            birth.getUTCMonth(),
            birth.getUTCDate(),
          ),
        );
        if (reference < birthdayThisYear) years -= 1;
        const anniversary = new Date(
          Date.UTC(
            birth.getUTCFullYear() + years,
            birth.getUTCMonth(),
            birth.getUTCDate(),
          ),
        );
        let months =
          (reference.getUTCFullYear() - anniversary.getUTCFullYear()) * 12 +
          reference.getUTCMonth() -
          anniversary.getUTCMonth();
        if (reference.getUTCDate() < anniversary.getUTCDate()) months -= 1;
        const monthStart = new Date(
          Date.UTC(
            anniversary.getUTCFullYear(),
            anniversary.getUTCMonth() + months,
            anniversary.getUTCDate(),
          ),
        );
        const days = Math.floor(
          (reference.valueOf() - monthStart.valueOf()) / 86_400_000,
        );
        setOutput(`${years} years, ${months} months, ${days} days`);
      } else if (slug === "gpa-calculator") {
        const points: Record<string, number> = { A: 4, B: 3, C: 2, D: 1, F: 0 };
        const grades = input
          .toUpperCase()
          .split(/[\s,;]+/u)
          .filter(Boolean)
          .map((grade) => {
            if (/^[0-4](?:\.\d+)?$/u.test(grade)) return Number(grade);
            const base = points[grade[0]];
            if (base === undefined || !/^[ABCDF][+-]?$/u.test(grade))
              throw new Error("Use grades A–F or grade points from 0 to 4.");
            return Math.min(
              4,
              Math.max(
                0,
                base +
                  (grade.endsWith("+") ? 0.3 : grade.endsWith("-") ? -0.3 : 0),
              ),
            );
          });
        if (!grades.length)
          throw new Error("Enter course grades separated by commas.");
        setOutput(
          `Unweighted GPA: ${(grades.reduce((sum, grade) => sum + grade, 0) / grades.length).toFixed(2)}\nCourses: ${grades.length}`,
        );
      } else if (slug === "calorie-calculator") {
        const [sex, ageText, weightText, heightText, activityText] =
          input.split(/[\s,;]+/u);
        const age = Number(ageText),
          weight = Number(weightText),
          height = Number(heightText),
          activity = Number(activityText);
        if (
          !sex ||
          ![age, weight, height, activity].every(Number.isFinite) ||
          age < 15 ||
          age > 100 ||
          weight <= 0 ||
          height <= 0 ||
          activity < 1.2 ||
          activity > 1.9
        )
          throw new Error(
            "Enter sex (M/F), age, weight in kg, height in cm, and activity factor 1.2–1.9.",
          );
        const bmr =
          10 * weight +
          6.25 * height -
          5 * age +
          (sex.toUpperCase() === "M"
            ? 5
            : sex.toUpperCase() === "F"
              ? -161
              : NaN);
        if (!Number.isFinite(bmr))
          throw new Error("Sex must be M or F for this equation.");
        setOutput(
          `Estimated BMR: ${Math.round(bmr)} kcal/day\nEstimated maintenance: ${Math.round(bmr * activity)} kcal/day\nThis is a formula-based estimate.`,
        );
      } else if (slug === "military-time") {
        const converted = input.split(/\r?\n/u).map((value) => {
          const text = value.trim();
          const twelve = /^(\d{1,2}):(\d{2})\s*(AM|PM)$/iu.exec(text);
          const twentyFour = /^(\d{1,2}):(\d{2})$/u.exec(text);
          let hours: number, minutes: number;
          if (twelve) {
            hours =
              (Number(twelve[1]) % 12) +
              (twelve[3].toUpperCase() === "PM" ? 12 : 0);
            minutes = Number(twelve[2]);
          } else if (twentyFour) {
            hours = Number(twentyFour[1]);
            minutes = Number(twentyFour[2]);
          } else throw new Error(`Invalid time: ${text}`);
          if (hours > 23 || minutes > 59)
            throw new Error(`Invalid time: ${text}`);
          const h12 = hours % 12 || 12;
          return `${text} → ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")} (${h12}:${String(minutes).padStart(2, "0")} ${hours < 12 ? "AM" : "PM"})`;
        });
        setOutput(converted.join("\n"));
      } else if (slug === "timezone-converter") {
        const [dateValue, zoneValue] = input.split(",");
        const date = new Date(dateValue.trim());
        const zone = zoneValue?.trim();
        if (Number.isNaN(date.valueOf()) || !zone)
          throw new Error(
            "Enter an ISO date/time and IANA time zone, separated by a comma.",
          );
        setOutput(
          new Intl.DateTimeFormat(undefined, {
            dateStyle: "full",
            timeStyle: "long",
            timeZone: zone,
          }).format(date),
        );
      } else if (slug === "case-converter") {
        const converted = {
          lower: input.toLocaleLowerCase(),
          upper: input.toLocaleUpperCase(),
          title: input.replace(/\b[\p{L}\p{N}]/gu, (letter) =>
            letter.toLocaleUpperCase(),
          ),
          sentence: input
            .toLocaleLowerCase()
            .replace(
              /(^|[.!?]\s+)(\p{L})/gu,
              (_match, prefix: string, letter: string) =>
                prefix + letter.toLocaleUpperCase(),
            ),
        }[caseMode];
        setOutput(converted);
      } else if (slug === "text-diff") {
        const separator = input.indexOf("\n---\n");
        if (separator < 0)
          throw new Error("Separate the two texts with a line containing ---.");
        const left = input.slice(0, separator).split("\n");
        const right = input.slice(separator + 5).split("\n");
        const count = Math.max(left.length, right.length);
        setOutput(
          Array.from({ length: count }, (_, index) => {
            if (left[index] === right[index]) return `  ${left[index] ?? ""}`;
            return `${left[index] === undefined ? "" : `- ${left[index]}\n`}${right[index] === undefined ? "" : `+ ${right[index]}`}`;
          }).join("\n"),
        );
      } else if (slug === "lorem-ipsum") {
        const count = Math.min(
          20,
          Math.max(1, Number.parseInt(input, 10) || 3),
        );
        const paragraph =
          "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.";
        setOutput(Array.from({ length: count }, () => paragraph).join("\n\n"));
      } else if (slug === "slug-generator") {
        setOutput(
          input
            .normalize("NFKD")
            .replace(/[\u0300-\u036f]/gu, "")
            .toLocaleLowerCase()
            .trim()
            .replace(/[^\p{L}\p{N}]+/gu, "-")
            .replace(/^-+|-+$/gu, ""),
        );
      } else if (slug === "sort-lines") {
        setOutput(
          [
            ...new Set(
              input
                .split(/\r?\n/u)
                .map((line) => line.trim())
                .filter(Boolean),
            ),
          ]
            .sort((a, b) => a.localeCompare(b))
            .join("\n"),
        );
      } else if (slug === "url-encoder") {
        setOutput(
          action === "encode"
            ? encodeURIComponent(input)
            : decodeURIComponent(input),
        );
      } else if (slug === "jwt-decoder") {
        const parts = input.trim().split(".");
        if (parts.length !== 3) throw new Error("Enter a three-part JWT.");
        const decodePart = (part: string) => {
          const binary = atob(
            part
              .replace(/-/gu, "+")
              .replace(/_/gu, "/")
              .padEnd(Math.ceil(part.length / 4) * 4, "="),
          );
          return JSON.parse(
            new TextDecoder().decode(
              Uint8Array.from(binary, (char) => char.charCodeAt(0)),
            ),
          );
        };
        setOutput(
          `Header\n${JSON.stringify(decodePart(parts[0]), null, 2)}\n\nPayload\n${JSON.stringify(decodePart(parts[1]), null, 2)}\n\nSignature is not verified.`,
        );
      } else if (slug === "hash-generator") {
        if (new TextEncoder().encode(input).byteLength > 1_000_000)
          throw new Error("Limit input to one megabyte.");
        if (hashAlgorithm === "MD5") setOutput(md5Hex(input));
        else {
          const digest = await crypto.subtle.digest(
            hashAlgorithm,
            new TextEncoder().encode(input),
          );
          setOutput(
            Array.from(new Uint8Array(digest), (byte) =>
              byte.toString(16).padStart(2, "0"),
            ).join(""),
          );
        }
      } else if (slug === "uuid-generator") {
        const count = Math.min(
          100,
          Math.max(1, Number.parseInt(input, 10) || 1),
        );
        setOutput(
          Array.from({ length: count }, () => crypto.randomUUID()).join("\n"),
        );
      } else if (slug === "timestamp-converter") {
        const numeric = Number(input.trim());
        const date =
          input.trim() !== "" && Number.isFinite(numeric)
            ? new Date(numeric * 1000)
            : new Date(input.trim());
        if (Number.isNaN(date.valueOf()))
          throw new Error("Enter a Unix timestamp in seconds or an ISO date.");
        setOutput(
          `ISO: ${date.toISOString()}\nUnix seconds: ${Math.floor(date.valueOf() / 1000)}`,
        );
      } else if (slug === "color-converter") {
        const match = /^#?([\da-f]{6})$/iu.exec(input.trim());
        if (!match)
          throw new Error("Enter a six-digit HEX color, such as #b94324.");
        const hex = match[1];
        const r = Number.parseInt(hex.slice(0, 2), 16);
        const g = Number.parseInt(hex.slice(2, 4), 16);
        const b = Number.parseInt(hex.slice(4, 6), 16);
        const rn = r / 255,
          gn = g / 255,
          bn = b / 255;
        const max = Math.max(rn, gn, bn),
          min = Math.min(rn, gn, bn),
          delta = max - min;
        const light = (max + min) / 2;
        let hue = 0;
        if (delta)
          hue =
            max === rn
              ? ((gn - bn) / delta) % 6
              : max === gn
                ? (bn - rn) / delta + 2
                : (rn - gn) / delta + 4;
        hue = (hue * 60 + 360) % 360;
        const saturation =
          delta === 0 ? 0 : delta / (1 - Math.abs(2 * light - 1));
        setOutput(
          `HEX: #${hex.toUpperCase()}\nRGB: rgb(${r}, ${g}, ${b})\nHSL: hsl(${Math.round(hue)}, ${Math.round(saturation * 100)}%, ${Math.round(light * 100)}%)`,
        );
      } else if (slug === "percentage-calculator") {
        const [percent, value] = input.split(/[\s,;]+/u).map(Number);
        if (![percent, value].every(Number.isFinite))
          throw new Error("Enter percentage and value, for example: 15, 80.");
        setOutput(
          `${percent}% of ${value} = ${((percent / 100) * value).toLocaleString()}`,
        );
      } else if (slug === "tip-calculator") {
        const [bill, percent = 15, people = 1] = input
          .split(/[\s,;]+/u)
          .map(Number);
        if (
          ![bill, percent, people].every(Number.isFinite) ||
          bill < 0 ||
          people < 1
        )
          throw new Error(
            "Enter bill, tip percentage, and people, for example: 50, 18, 2.",
          );
        const tip = (bill * percent) / 100;
        setOutput(
          `Tip: ${tip.toFixed(2)}\nTotal: ${(bill + tip).toFixed(2)}\nPer person: ${((bill + tip) / people).toFixed(2)}`,
        );
      } else if (slug === "loan-calculator") {
        const [principal, annualRate, months] = input
          .split(/[\s,;]+/u)
          .map(Number);
        if (
          ![principal, annualRate, months].every(Number.isFinite) ||
          principal <= 0 ||
          annualRate < 0 ||
          months < 1 ||
          months > 600 ||
          !Number.isInteger(months)
        )
          throw new Error(
            "Enter principal, annual APR (0 or higher), and a whole number of months (1–600).",
          );
        const monthlyRate = annualRate / 1200;
        const payment =
          monthlyRate === 0
            ? principal / months
            : (principal * monthlyRate) / (1 - (1 + monthlyRate) ** -months);
        setOutput(
          `Estimated monthly payment: ${payment.toFixed(2)}\nTotal paid: ${(payment * months).toFixed(2)}\nInterest: ${(payment * months - principal).toFixed(2)}\nEstimate excludes fees and may differ from a lender's offer.`,
        );
      } else if (slug === "mortgage-calculator") {
        const [price, downPayment, annualRate, years] = input
          .split(/[\s,;]+/u)
          .map(Number);
        if (
          ![price, downPayment, annualRate, years].every(Number.isFinite) ||
          price <= 0 ||
          downPayment < 0 ||
          downPayment >= price ||
          annualRate < 0 ||
          years <= 0 ||
          years > 50
        )
          throw new Error(
            "Enter home price, down payment, annual APR, and term in years (up to 50).",
          );
        const principal = price - downPayment;
        const months = Math.round(years * 12);
        const monthlyRate = annualRate / 1200;
        const payment =
          monthlyRate === 0
            ? principal / months
            : (principal * monthlyRate) / (1 - (1 + monthlyRate) ** -months);
        setOutput(
          `Estimated principal and interest: ${payment.toFixed(2)} / month\nLoan amount: ${principal.toFixed(2)}\nTotal paid: ${(payment * months).toFixed(2)}\nInterest: ${(payment * months - principal).toFixed(2)}\nExcludes property taxes, insurance, HOA fees, and closing costs.`,
        );
      } else if (slug === "date-difference") {
        const dates = input.split(/[\s,;]+/u).map((value) => new Date(value));
        if (
          dates.length !== 2 ||
          dates.some((date) => Number.isNaN(date.valueOf()))
        )
          throw new Error(
            "Enter two dates, for example: 2026-01-01, 2026-12-31.",
          );
        setOutput(
          `${Math.abs(Math.round((dates[1].valueOf() - dates[0].valueOf()) / 86_400_000))} days`,
        );
      } else if (slug === "date-countdown") {
        const value = input.trim();
        const target = new Date(`${value}T00:00:00Z`);
        if (
          !/^\d{4}-\d{2}-\d{2}$/u.test(value) ||
          Number.isNaN(target.valueOf()) ||
          target.toISOString().slice(0, 10) !== value
        )
          throw new Error("Enter a calendar date as YYYY-MM-DD.");
        const today = new Date();
        const currentDay = Date.UTC(
          today.getUTCFullYear(),
          today.getUTCMonth(),
          today.getUTCDate(),
        );
        const days = Math.round((target.valueOf() - currentDay) / 86_400_000);
        setOutput(
          days === 0
            ? "That date is today."
            : `${Math.abs(days)} days ${days > 0 ? "until" : "since"} ${value}.`,
        );
      } else if (slug === "unit-converter") {
        const match =
          /^\s*(-?\d+(?:\.\d+)?)\s*(mm|cm|m|km|in|ft|yd|mi)\s*$/iu.exec(input);
        if (!match)
          throw new Error(
            "Enter a value and unit: mm, cm, m, km, in, ft, yd, or mi.",
          );
        const meters: Record<string, number> = {
          mm: 0.001,
          cm: 0.01,
          m: 1,
          km: 1000,
          in: 0.0254,
          ft: 0.3048,
          yd: 0.9144,
          mi: 1609.344,
        };
        const value = Number(match[1]) * meters[match[2].toLowerCase()];
        setOutput(
          `Millimeters: ${(value * 1000).toPrecision(6)}\nCentimeters: ${(value * 100).toPrecision(6)}\nMeters: ${value.toPrecision(6)}\nKilometers: ${(value / 1000).toPrecision(6)}\nFeet: ${(value / meters.ft).toPrecision(6)}\nMiles: ${(value / meters.mi).toPrecision(6)}`,
        );
      } else if (slug === "base64") {
        if (action === "decode")
          setOutput(
            new TextDecoder().decode(
              Uint8Array.from(atob(input.trim()), (character) =>
                character.charCodeAt(0),
              ),
            ),
          );
        else {
          const bytes = new TextEncoder().encode(input);
          let binary = "";
          for (let offset = 0; offset < bytes.length; offset += 0x8000)
            binary += String.fromCharCode(
              ...bytes.subarray(offset, offset + 0x8000),
            );
          setOutput(btoa(binary));
        }
      } else if (slug === "qr-static") {
        setBusy(true);
        setQr(
          await QRCode.toDataURL(input, {
            width: 320,
            margin: 2,
            errorCorrectionLevel: "M",
          }),
        );
        setOutput("");
      } else if (slug === "barcode-generator") {
        if (!barcodeRef.current)
          throw new Error("Barcode preview is unavailable.");
        const { default: JsBarcode } = await import("jsbarcode");
        JsBarcode(barcodeRef.current, input.trim(), {
          format: "CODE128",
          displayValue: true,
          fontSize: 16,
          margin: 12,
          height: 100,
          lineColor: "#111827",
        });
        setBarcodeReady(true);
        setOutput("");
      } else if (slug === "email-signature") {
        setOutput(signatureHtml);
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not process this input. Check the text and try again.",
      );
      setOutput("");
    } finally {
      setBusy(false);
    }
  }

  function generatePassword() {
    const alphabet =
      "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*_-+";
    const acceptedBelow =
      Math.floor(0x1_0000_0000 / alphabet.length) * alphabet.length;
    let password = "";
    while (password.length < length) {
      const random = new Uint32Array((length - password.length) * 2);
      window.crypto.getRandomValues(random);
      for (const value of random) {
        if (value < acceptedBelow)
          password += alphabet[value % alphabet.length];
        if (password.length === length) break;
      }
    }
    setOutput(password);
    setError("");
  }

  const words = input.trim() ? input.trim().split(/\s+/u).length : 0;
  const characters = input.length;
  const sentences = input.trim()
    ? (input.match(/[.!?]+(?=\s|$)/gu) ?? []).length
    : 0;
  const paragraphs = input.trim() ? input.trim().split(/\n\s*\n/u).length : 0;

  async function downloadBarcode() {
    if (!barcodeRef.current) return;
    barcodeRef.current.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    const data = new XMLSerializer().serializeToString(barcodeRef.current);
    const url = URL.createObjectURL(
      new Blob([data], { type: "image/svg+xml" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "rendercart-barcode.svg";
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <section className="mt-8 rounded-2xl border border-line bg-surface p-6  ">
      {slug === "word-counter" ? (
        <>
          <label className="block text-sm font-semibold">
            Your text
            <textarea
              className="mt-3 min-h-56 w-full rounded-xl border border-line-strong bg-transparent p-3 font-normal "
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Start typing or paste your text…"
            />
          </label>
          <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Words", words],
              ["Characters", characters],
              ["Sentences", sentences],
              ["Paragraphs", paragraphs],
            ].map(([name, count]) => (
              <div key={name} className="rounded-xl bg-canvas p-4 ">
                <dt className="text-xs text-muted">{name}</dt>
                <dd className="mt-1 text-2xl font-semibold">{count}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : [
          "image-crop",
          "image-resize",
          "image-rotate",
          "color-picker",
          "favicon-generator",
          "exif-viewer",
          "meme-maker",
        ].includes(slug) ? (
        <ClientImageTools slug={slug} />
      ) : slug === "password-generator" ? (
        <>
          <label className="block text-sm font-semibold">
            Password length: {length}
            <input
              className="mt-3 block w-full accent-accent"
              type="range"
              min={12}
              max={64}
              value={length}
              onChange={(event) => setLength(Number(event.target.value))}
            />
          </label>
          <button
            className="mt-5 rounded-xl bg-accent px-5 py-3 font-semibold text-white"
            onClick={generatePassword}
          >
            Generate password
          </button>
        </>
      ) : slug === "email-signature" ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            {(
              ["name", "title", "company", "email", "phone", "website"] as const
            ).map((key) => (
              <label
                key={key}
                className="block text-sm font-semibold capitalize"
              >
                {key}
                <input
                  className="mt-2 block w-full rounded-xl border border-line-strong bg-transparent px-3 py-2 font-normal "
                  value={signature[key]}
                  onChange={(event) =>
                    setSignature((current) => ({
                      ...current,
                      [key]: event.target.value,
                    }))
                  }
                />
              </label>
            ))}
          </div>
          <div
            className="mt-5 rounded-xl border border-line bg-surface p-5"
            aria-label="Signature preview"
          >
            <p className="text-base font-bold text-ink">
              {signature.name || "Your Name"}
            </p>
            <p className="mt-1 text-sm text-muted">
              {[signature.title, signature.company]
                .filter(Boolean)
                .join(" · ") || "Title · Company"}
            </p>
            <p className="mt-2 text-xs text-muted">
              {[signature.email, signature.phone, signature.website]
                .filter(Boolean)
                .join(" | ")}
            </p>
          </div>
          <button
            className="mt-5 rounded-xl bg-accent px-5 py-3 font-semibold text-white"
            onClick={() => {
              setOutput(signatureHtml);
              void navigator.clipboard.writeText(signatureHtml);
            }}
          >
            Copy HTML signature
          </button>
        </>
      ) : (
        <>
          {slug === "case-converter" && (
            <label className="mb-4 block text-sm font-semibold">
              Letter case
              <select
                value={caseMode}
                onChange={(event) =>
                  setCaseMode(event.target.value as typeof caseMode)
                }
                className="mt-2 block rounded-xl border border-line-strong bg-transparent px-3 py-2 "
              >
                <option value="lower">lowercase</option>
                <option value="upper">UPPERCASE</option>
                <option value="title">Title Case</option>
                <option value="sentence">Sentence case</option>
              </select>
            </label>
          )}
          {slug === "hash-generator" && (
            <label className="mb-4 block text-sm font-semibold">
              Hash algorithm
              <select
                value={hashAlgorithm}
                onChange={(event) =>
                  setHashAlgorithm(event.target.value as typeof hashAlgorithm)
                }
                className="mt-2 block rounded-xl border border-line-strong bg-transparent px-3 py-2 "
              >
                <option value="MD5">MD5 (legacy only)</option>
                <option value="SHA-256">SHA-256</option>
                <option value="SHA-1">SHA-1</option>
              </select>
              <span className="mt-2 block font-normal text-muted">
                MD5 and SHA-1 are for compatibility checks only; do not use them
                for security.
              </span>
            </label>
          )}
          {slug === "currency-converter" && currencyRates && (
            <div className="mb-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm font-semibold">
                From
                <select
                  value={sourceCurrency}
                  onChange={(event) => setSourceCurrency(event.target.value)}
                  className="mt-2 block w-full rounded-xl border border-line-strong bg-transparent px-3 py-2 "
                >
                  {Object.keys(currencyRates.rates)
                    .sort()
                    .map((code) => (
                      <option key={code} value={code}>
                        {code}
                      </option>
                    ))}
                </select>
              </label>
              <label className="text-sm font-semibold">
                To
                <select
                  value={targetCurrency}
                  onChange={(event) => setTargetCurrency(event.target.value)}
                  className="mt-2 block w-full rounded-xl border border-line-strong bg-transparent px-3 py-2 "
                >
                  {Object.keys(currencyRates.rates)
                    .sort()
                    .map((code) => (
                      <option key={code} value={code}>
                        {code}
                      </option>
                    ))}
                </select>
              </label>
              <p className="text-xs text-muted sm:col-span-2">
                ECB reference rates for {currencyRates.as_of}
                {currencyRates.stale ? " · cached rates" : ""}. Indicative only;
                not for transaction pricing.
              </p>
            </div>
          )}
          {[
            "base64",
            "url-encoder",
            "markdown-html",
            "json-csv",
            "json-yaml",
          ].includes(slug) && (
            <div className="mb-4 flex gap-2">
              <button
                className={`rounded-lg px-3 py-2 text-sm ${action === "encode" ? "bg-accent-soft text-accent" : "bg-subtle "}`}
                onClick={() => setAction("encode")}
              >
                {slug === "markdown-html"
                  ? "Markdown → HTML"
                  : slug === "json-csv"
                    ? "JSON → CSV"
                    : slug === "json-yaml"
                      ? "JSON → YAML"
                      : "Encode"}
              </button>
              <button
                className={`rounded-lg px-3 py-2 text-sm ${action === "decode" ? "bg-accent-soft text-accent" : "bg-subtle "}`}
                onClick={() => setAction("decode")}
              >
                {slug === "markdown-html"
                  ? "HTML → Markdown"
                  : slug === "json-csv"
                    ? "CSV → JSON"
                    : slug === "json-yaml"
                      ? "YAML → JSON"
                      : "Decode"}
              </button>
            </div>
          )}
          <label className="block text-sm font-semibold">
            {slug === "qr-static"
              ? "Text or URL"
              : slug === "barcode-generator"
                ? "Barcode value (Code 128)"
                : slug === "text-diff"
                  ? "First text, then a line with ---, then second text"
                  : slug === "percentage-calculator"
                    ? "Percentage, value (example: 15, 80)"
                    : slug === "tip-calculator"
                      ? "Bill, tip percentage, people (example: 50, 18, 2)"
                      : slug === "loan-calculator"
                        ? "Principal, APR %, term in months (example: 25000, 7.5, 60)"
                        : slug === "mortgage-calculator"
                          ? "Home price, down payment, APR %, term in years"
                          : slug === "date-difference"
                            ? "Two ISO dates (example: 2026-01-01, 2026-12-31)"
                            : slug === "date-countdown"
                              ? "Target date (YYYY-MM-DD)"
                              : slug === "unit-converter"
                                ? "Value and unit (example: 12 km)"
                                : slug === "uuid-generator"
                                  ? "Number of UUIDs (optional, default 1)"
                                  : slug === "lorem-ipsum"
                                    ? "Number of paragraphs (optional, default 3)"
                                    : slug === "timestamp-converter"
                                      ? "Unix timestamp in seconds or an ISO date"
                                      : slug === "color-converter"
                                        ? "Six-digit HEX color (example: #b94324)"
                                        : slug === "regex-tester"
                                          ? "Pattern and optional flags, then ---, then sample text"
                                          : slug === "cron-builder"
                                            ? "Five fields (example: 0 9 * * 1-5)"
                                            : slug === "age-calculator"
                                              ? "Birth date, optional reference date (YYYY-MM-DD)"
                                              : slug === "gpa-calculator"
                                                ? "Grades separated by commas (example: A, B+, 3.5)"
                                                : slug === "calorie-calculator"
                                                  ? "M/F, age, weight kg, height cm, activity factor"
                                                  : slug === "military-time"
                                                    ? "Times such as 2:30 PM or 14:30, one per line"
                                                    : slug ===
                                                        "timezone-converter"
                                                      ? "ISO date/time, IANA time zone (e.g. 2026-10-18T13:00, America/Winnipeg)"
                                                      : slug === "markdown-html"
                                                        ? "Markdown or HTML input"
                                                        : slug === "json-csv"
                                                          ? "JSON array of objects or CSV with a header row"
                                                          : slug === "json-yaml"
                                                            ? "JSON value or YAML document"
                                                            : slug ===
                                                                "currency-converter"
                                                              ? "Amount to convert"
                                                              : "Input"}
            <textarea
              className="mt-3 min-h-40 w-full rounded-xl border border-line-strong bg-transparent p-3 font-normal "
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={
                slug === "json-formatter"
                  ? '{ "hello": "world" }'
                  : slug === "loan-calculator"
                    ? "25000, 7.5, 60"
                    : slug === "mortgage-calculator"
                      ? "400000, 80000, 6.5, 30"
                      : slug === "date-countdown"
                        ? "2027-01-01"
                        : slug === "json-csv"
                          ? '[{"name":"Ada","role":"Engineer"}]'
                          : slug === "json-yaml"
                            ? '{"name":"Ada","active":true,"skills":["Python","TypeScript"]}'
                            : slug === "regex-tester"
                              ? "\\bcat\\b\ngi\n---\nThe cat sat by the catalog."
                              : slug === "url-encoder"
                                ? "Text to encode or encoded URL component…"
                                : slug === "currency-converter"
                                  ? "100"
                                  : "Enter text…"
              }
            />
          </label>
          <button
            disabled={
              (!input &&
                !["uuid-generator", "lorem-ipsum", "hash-generator"].includes(
                  slug,
                )) ||
              busy ||
              (slug === "currency-converter" && !currencyRates)
            }
            className="mt-5 rounded-xl bg-accent px-5 py-3 font-semibold text-white disabled:opacity-50"
            onClick={() => void run()}
          >
            {busy
              ? "Creating…"
              : slug === "qr-static"
                ? "Create QR code"
                : slug === "barcode-generator"
                  ? "Create barcode"
                  : slug === "json-formatter"
                    ? "Format JSON"
                    : slug === "currency-converter"
                      ? "Convert currency"
                      : slug === "regex-tester"
                        ? "Test regex"
                        : slug === "cron-builder"
                          ? "Validate schedule"
                          : slug === "age-calculator"
                            ? "Calculate age"
                            : slug === "gpa-calculator"
                              ? "Calculate GPA"
                              : slug === "calorie-calculator"
                                ? "Estimate calories"
                                : slug === "military-time"
                                  ? "Convert time"
                                  : slug === "timezone-converter"
                                    ? "Convert time zone"
                                    : slug === "loan-calculator"
                                      ? "Estimate loan payment"
                                      : slug === "mortgage-calculator"
                                        ? "Estimate mortgage payment"
                                        : slug === "date-countdown"
                                          ? "Count days"
                                          : slug === "base64" ||
                                              slug === "url-encoder"
                                            ? `${action === "encode" ? "Encode" : "Decode"} ${slug === "base64" ? "Base64" : "URL component"}`
                                            : slug === "markdown-html" ||
                                                slug === "json-csv" ||
                                                slug === "json-yaml"
                                              ? "Convert"
                                              : slug === "uuid-generator"
                                                ? "Generate UUIDs"
                                                : slug === "lorem-ipsum"
                                                  ? "Generate paragraphs"
                                                  : "Convert"}
          </button>
          {slug === "barcode-generator" && (
            <div className="mt-6 overflow-x-auto rounded-xl bg-surface p-4">
              <svg ref={barcodeRef} aria-label="Generated Code 128 barcode" />
              {barcodeReady && (
                <button
                  className="mt-4 block text-sm font-semibold text-accent"
                  onClick={() => void downloadBarcode()}
                >
                  Download SVG
                </button>
              )}
            </div>
          )}
        </>
      )}
      {error && (
        <p role="alert" className="mt-4 text-sm text-red-600">
          {error}
        </p>
      )}
      {slug === "currency-converter" && currencyRatesError && (
        <p role="status" className="mt-4 text-sm text-amber-700">
          {currencyRatesError}
        </p>
      )}
      {qr && (
        <div className="mt-6">
          <Image
            className="h-64 w-64 rounded-xl border border-line bg-surface p-2"
            src={qr}
            width={256}
            height={256}
            unoptimized
            alt="Generated QR code"
          />
          <a
            className="mt-3 inline-block text-sm font-semibold text-accent "
            href={qr}
            download="rendercart-qr.png"
          >
            Download PNG
          </a>
        </div>
      )}
      {output && (
        <div className="mt-6">
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-all rounded-xl bg-canvas p-4 text-sm ">
            {output}
          </pre>
          <button
            className="mt-3 text-sm font-semibold text-accent "
            onClick={() => void navigator.clipboard.writeText(output)}
          >
            Copy result
          </button>
        </div>
      )}
    </section>
  );
}
