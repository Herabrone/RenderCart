export type ClientTool = {
  slug: string;
  name: string;
  category: string;
  summary: string;
  runtime: "client";
  inputs: null;
  options_schema: null;
  seo: { title: string; description: string };
};

const additionalTools: Array<[string, string, string, string]> = [
  ["case-converter", "Case Converter", "writing", "Convert text between common letter cases."],
  ["text-diff", "Text Compare", "writing", "Compare two text blocks locally in your browser."],
  ["lorem-ipsum", "Lorem Ipsum Generator", "writing", "Generate placeholder paragraphs without a server request."],
  ["slug-generator", "Slug Generator", "writing", "Turn a title into a clean URL slug."],
  ["sort-lines", "Sort and Remove Duplicate Lines", "writing", "Sort lines and remove duplicates locally."],
  ["url-encoder", "URL Encoder / Decoder", "developer", "Encode or decode URL components in your browser."],
  ["jwt-decoder", "JWT Decoder", "developer", "Inspect a JWT header and payload locally; signatures are not verified."],
  ["hash-generator", "Hash Generator", "developer", "Calculate MD5, SHA-1, or SHA-256 digests locally in your browser."],
  ["uuid-generator", "UUID Generator", "developer", "Generate version 4 UUIDs with browser cryptography."],
  ["timestamp-converter", "Timestamp Converter", "developer", "Convert Unix timestamps and ISO dates."],
  ["color-converter", "Color Converter", "developer", "Convert a HEX color into RGB and HSL values."],
  ["percentage-calculator", "Percentage Calculator", "calculators", "Calculate a percentage of a value."],
  ["tip-calculator", "Tip Calculator", "calculators", "Calculate tip, total, and per-person amounts."],
  ["loan-calculator", "Loan Payment Calculator", "calculators", "Estimate fixed monthly loan payments from principal, APR, and term."],
  ["mortgage-calculator", "Mortgage Payment Calculator", "calculators", "Estimate principal and interest from home price, down payment, APR, and term."],
  ["date-difference", "Date Difference Calculator", "calculators", "Find the days between two dates."],
  ["date-countdown", "Date Countdown", "calculators", "Count the days until or since a calendar date."],
  ["unit-converter", "Length Converter", "calculators", "Convert common metric and imperial length units."],
  ["markdown-html", "Markdown / HTML Converter", "developer", "Convert basic Markdown to safe HTML or HTML to Markdown."],
  ["json-csv", "JSON / CSV Converter", "developer", "Convert arrays of JSON objects and CSV locally."],
  ["regex-tester", "Regex Tester", "developer", "Test a regular expression locally in a time-limited worker."],
  ["cron-builder", "Cron Expression Builder", "developer", "Validate a five-field cron expression and explain its fields."],
  ["age-calculator", "Age Calculator", "calculators", "Calculate age in years, months, and days."],
  ["gpa-calculator", "GPA Calculator", "calculators", "Calculate a simple unweighted GPA from course grades."],
  ["calorie-calculator", "Calorie Calculator", "calculators", "Estimate BMR and daily calories with the Mifflin-St Jeor equation."],
  ["military-time", "Military Time Converter", "calculators", "Convert 12-hour and 24-hour clock times."],
  ["timezone-converter", "Time Zone Converter", "calculators", "Format an ISO date and time in an IANA time zone."],
  ["json-yaml", "JSON / YAML Converter", "developer", "Convert JSON to YAML or YAML to formatted JSON locally in your browser."],
  ["currency-converter", "Currency Converter", "calculators", "Convert currencies using daily cached European Central Bank reference rates."],
  ["image-crop", "Image Cropper", "image", "Crop an image locally to a selected aspect ratio."],
  ["image-resize", "Image Resizer", "image", "Resize an image in your browser and download the result."],
  ["image-rotate", "Image Rotator", "image", "Rotate an image locally without uploading it."],
  ["color-picker", "Image Color Palette", "image", "Sample the dominant colors from a local image."],
  ["favicon-generator", "Favicon Generator", "image", "Create a 32-pixel PNG favicon from an image."],
  ["exif-viewer", "EXIF Viewer and Remover", "image", "Inspect basic JPEG metadata or re-encode an image without metadata."],
  ["meme-maker", "Meme Maker", "image", "Add top and bottom captions to an image locally."],
];

export const clientTools: ClientTool[] = [
  {
    slug: "word-counter",
    name: "Word Counter",
    category: "writing",
    summary: "Count words, characters, sentences, and paragraphs as you write.",
    runtime: "client",
    inputs: null,
    options_schema: null,
    seo: {
      title: "Word Counter | RenderCart",
      description: "Count words and characters instantly in your browser.",
    },
  },
  {
    slug: "json-formatter",
    name: "JSON Formatter",
    category: "developer",
    summary: "Format and validate JSON locally in your browser.",
    runtime: "client",
    inputs: null,
    options_schema: null,
    seo: {
      title: "JSON Formatter & Validator | RenderCart",
      description: "Format, validate, and inspect JSON in your browser.",
    },
  },
  {
    slug: "qr-static",
    name: "Static QR Code",
    category: "business",
    summary: "Create a downloadable QR code without uploading its contents.",
    runtime: "client",
    inputs: null,
    options_schema: null,
    seo: {
      title: "Free QR Code Generator | RenderCart",
      description: "Create a static QR code privately in your browser.",
    },
  },
  {
    slug: "qr-dynamic",
    name: "Dynamic QR Codes",
    category: "business",
    summary:
      "Create editable QR links and review scan time, country, and device analytics.",
    runtime: "client",
    inputs: null,
    options_schema: null,
    seo: {
      title: "Dynamic QR Code Generator | RenderCart",
      description: "Create editable QR codes and review scan analytics.",
    },
  },
  {
    slug: "barcode-generator",
    name: "Barcode Generator",
    category: "business",
    summary:
      "Create Code 128 barcodes directly in your browser and download them as SVG.",
    runtime: "client",
    inputs: null,
    options_schema: null,
    seo: {
      title: "Free Barcode Generator | RenderCart",
      description:
        "Generate and download Code 128 barcodes privately in your browser.",
    },
  },
  {
    slug: "email-signature",
    name: "Email Signature Generator",
    category: "business",
    summary:
      "Create a clean HTML email signature and copy it into your email client.",
    runtime: "client",
    inputs: null,
    options_schema: null,
    seo: {
      title: "Email Signature Generator | RenderCart",
      description: "Build and copy an HTML email signature in your browser.",
    },
  },
  {
    slug: "base64",
    name: "Base64 Encoder / Decoder",
    category: "developer",
    summary: "Encode or decode UTF-8 text locally.",
    runtime: "client",
    inputs: null,
    options_schema: null,
    seo: {
      title: "Base64 Encoder & Decoder | RenderCart",
      description: "Encode and decode Base64 text in your browser.",
    },
  },
  {
    slug: "password-generator",
    name: "Password Generator",
    category: "developer",
    summary:
      "Generate a random password using your browser's secure random source.",
    runtime: "client",
    inputs: null,
    options_schema: null,
    seo: {
      title: "Secure Password Generator | RenderCart",
      description:
        "Generate a random password locally using browser cryptography.",
    },
  },
  ...additionalTools.map(([slug, name, category, summary]) => ({
    slug,
    name,
    category,
    summary,
    runtime: "client" as const,
    inputs: null,
    options_schema: null,
    seo: { title: `${name} | RenderCart`, description: summary },
  })),
];
