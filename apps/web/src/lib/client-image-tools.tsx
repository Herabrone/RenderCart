"use client";

/* eslint-disable @next/next/no-img-element -- These previews use local blob URLs and must stay in-browser. */

import { ChangeEvent, useEffect, useState } from "react";

type ExifInfo = { orientation?: number; dateTime?: string };

async function jpegExif(file: File): Promise<ExifInfo> {
  const bytes = new DataView(await file.arrayBuffer());
  const info: ExifInfo = {};
  if (bytes.byteLength < 4 || bytes.getUint16(0) !== 0xffd8) return info;
  let offset = 2;
  while (offset + 4 <= bytes.byteLength) {
    if (bytes.getUint8(offset) !== 0xff) break;
    const marker = bytes.getUint8(offset + 1);
    const segmentLength = bytes.getUint16(offset + 2);
    if (segmentLength < 2 || offset + 2 + segmentLength > bytes.byteLength)
      break;
    const segment = offset + 4;
    if (
      marker === 0xe1 &&
      segment + 14 <= bytes.byteLength &&
      bytes.getUint32(segment) === 0x45786966 &&
      bytes.getUint16(segment + 4) === 0
    ) {
      const tiff = segment + 6;
      const littleEndian = bytes.getUint16(tiff) === 0x4949;
      const read16 = (position: number) =>
        bytes.getUint16(position, littleEndian);
      const read32 = (position: number) =>
        bytes.getUint32(position, littleEndian);
      if (read16(tiff + 2) !== 42) return info;
      const ifd = tiff + read32(tiff + 4);
      const entries = read16(ifd);
      for (let index = 0; index < entries; index += 1) {
        const entry = ifd + 2 + index * 12;
        if (entry + 12 > bytes.byteLength) break;
        const tag = read16(entry);
        if (tag === 0x0112) info.orientation = read16(entry + 8);
        if (tag === 0x0132) {
          const valueOffset = tiff + read32(entry + 8);
          const count = Math.min(read32(entry + 4), 32);
          if (valueOffset + count <= bytes.byteLength) {
            const chars = Array.from({ length: count }, (_, i) =>
              bytes.getUint8(valueOffset + i),
            );
            info.dateTime = new TextDecoder()
              .decode(new Uint8Array(chars))
              .replace(/\0+$/u, "");
          }
        }
      }
      return info;
    }
    offset += 2 + segmentLength;
  }
  return info;
}

function canvasBlob(canvas: HTMLCanvasElement, type: string): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) =>
        blob
          ? resolve(blob)
          : reject(new Error("Could not encode this image.")),
      type,
      0.92,
    );
  });
}

export function ClientImageTools({ slug }: { slug: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [resultUrl, setResultUrl] = useState("");
  const [width, setWidth] = useState("1024");
  const [height, setHeight] = useState("1024");
  const [aspect, setAspect] = useState("1:1");
  const [rotation, setRotation] = useState("90");
  const [topText, setTopText] = useState("");
  const [bottomText, setBottomText] = useState("");
  const [exifAction, setExifAction] = useState<"view" | "remove">("view");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(
    () => () => {
      if (sourceUrl) URL.revokeObjectURL(sourceUrl);
      if (resultUrl) URL.revokeObjectURL(resultUrl);
    },
    [sourceUrl, resultUrl],
  );

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setError("");
    setMessage("");
    setFile(null);
    setResultUrl("");
    setSourceUrl(selected ? URL.createObjectURL(selected) : "");
    if (!selected) return;
    if (
      !selected.type.startsWith("image/") ||
      selected.size > 25 * 1024 * 1024
    ) {
      setError("Choose an image file no larger than 25 MB.");
      setSourceUrl("");
      return;
    }
    setFile(selected);
  }

  async function process() {
    if (!file || !sourceUrl) return;
    setError("");
    setMessage("");
    try {
      if (slug === "exif-viewer" && exifAction === "view") {
        const info = await jpegExif(file);
        setMessage(
          file.type === "image/jpeg"
            ? `JPEG metadata found:\nOrientation: ${info.orientation ?? "not present"}\nDate taken: ${info.dateTime ?? "not present"}`
            : "EXIF inspection currently reads JPEG orientation and date fields. This file is not a JPEG.",
        );
        return;
      }
      const image = new Image();
      image.src = sourceUrl;
      await image.decode();
      if (image.naturalWidth * image.naturalHeight > 40_000_000)
        throw new Error(
          "This image exceeds the 40 megapixel browser processing limit.",
        );
      if (slug === "color-picker") {
        const sample = document.createElement("canvas");
        sample.width = 64;
        sample.height = 64;
        const context = sample.getContext("2d", { willReadFrequently: true });
        if (!context)
          throw new Error("Image sampling is unavailable in this browser.");
        context.drawImage(image, 0, 0, sample.width, sample.height);
        const pixels = context.getImageData(
          0,
          0,
          sample.width,
          sample.height,
        ).data;
        const counts = new Map<string, number>();
        for (let index = 0; index < pixels.length; index += 4) {
          if (pixels[index + 3] < 32) continue;
          const channel = (value: number) => Math.round(value / 32) * 32;
          const color = [
            channel(pixels[index]),
            channel(pixels[index + 1]),
            channel(pixels[index + 2]),
          ]
            .map((part) => Math.min(255, part).toString(16).padStart(2, "0"))
            .join("");
          counts.set(color, (counts.get(color) ?? 0) + 1);
        }
        setMessage(
          [...counts.entries()]
            .sort((a, b) => b[1] - a[1])
            .slice(0, 8)
            .map(
              ([color, count]) => `#${color.toUpperCase()} · ${count} samples`,
            )
            .join("\n"),
        );
        return;
      }

      let cropX = 0,
        cropY = 0,
        cropWidth = image.naturalWidth,
        cropHeight = image.naturalHeight;
      if (slug === "image-crop" || slug === "favicon-generator") {
        let ratio = 1;
        if (slug === "image-crop") {
          const [numerator, denominator] = aspect.split(":").map(Number);
          if (
            ![numerator, denominator].every(
              (part) => Number.isFinite(part) && part > 0,
            )
          )
            throw new Error("Enter a positive aspect ratio such as 16:9.");
          ratio = numerator / denominator;
        }
        const imageRatio = cropWidth / cropHeight;
        if (imageRatio > ratio) {
          const nextWidth = cropHeight * ratio;
          cropX = (cropWidth - nextWidth) / 2;
          cropWidth = nextWidth;
        } else {
          const nextHeight = cropWidth / ratio;
          cropY = (cropHeight - nextHeight) / 2;
          cropHeight = nextHeight;
        }
      }

      let outputWidth = cropWidth,
        outputHeight = cropHeight;
      if (slug === "image-resize") {
        const requestedWidth = Number(width),
          requestedHeight = Number(height);
        if (
          ![requestedWidth, requestedHeight].every(
            (value) => Number.isInteger(value) && value > 0 && value <= 4096,
          )
        )
          throw new Error("Set width and height from 1 to 4096 pixels.");
        const scale = Math.min(
          requestedWidth / cropWidth,
          requestedHeight / cropHeight,
        );
        outputWidth = Math.max(1, Math.round(cropWidth * scale));
        outputHeight = Math.max(1, Math.round(cropHeight * scale));
      } else if (slug === "favicon-generator") {
        outputWidth = 32;
        outputHeight = 32;
      }

      const angle = slug === "image-rotate" ? Number(rotation) : 0;
      if (!Number.isFinite(angle) || angle % 90 !== 0 || Math.abs(angle) > 270)
        throw new Error("Rotation must be 0, 90, 180, or 270 degrees.");
      const quarterTurn = Math.abs(angle) % 180 === 90;
      const captionWidth =
        slug === "meme-maker" ? Math.min(900, image.naturalWidth) : 0;
      const scaleMeme =
        slug === "meme-maker" ? captionWidth / image.naturalWidth : 1;
      const canvas = document.createElement("canvas");
      canvas.width = Math.ceil(
        (quarterTurn ? outputHeight : outputWidth) *
          (slug === "meme-maker" ? scaleMeme : 1),
      );
      canvas.height = Math.ceil(
        (quarterTurn ? outputWidth : outputHeight) *
          (slug === "meme-maker" ? scaleMeme : 1),
      );
      const context = canvas.getContext("2d");
      if (!context)
        throw new Error("Image processing is unavailable in this browser.");
      if (slug === "image-rotate") {
        context.translate(canvas.width / 2, canvas.height / 2);
        context.rotate((angle * Math.PI) / 180);
        context.drawImage(
          image,
          -image.naturalWidth / 2,
          -image.naturalHeight / 2,
        );
      } else {
        context.drawImage(
          image,
          cropX,
          cropY,
          cropWidth,
          cropHeight,
          0,
          0,
          canvas.width,
          canvas.height,
        );
      }
      if (slug === "meme-maker") {
        context.font = `bold ${Math.max(20, Math.round(canvas.width / 12))}px Impact, sans-serif`;
        context.textAlign = "center";
        context.lineWidth = Math.max(2, canvas.width / 100);
        context.strokeStyle = "black";
        context.fillStyle = "white";
        const captions: Array<[string, number]> = [
          [topText, canvas.width / 12],
          [bottomText, canvas.height - canvas.width / 36],
        ];
        for (const [text, y] of captions) {
          if (!text) continue;
          const clipped = text.toUpperCase().slice(0, 100);
          context.strokeText(clipped, canvas.width / 2, y, canvas.width - 20);
          context.fillText(clipped, canvas.width / 2, y, canvas.width - 20);
        }
      }
      const outputType =
        file.type === "image/jpeg" && slug !== "exif-viewer"
          ? "image/jpeg"
          : "image/png";
      const blob = await canvasBlob(canvas, outputType);
      setResultUrl(URL.createObjectURL(blob));
      setMessage("Processed locally in your browser.");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not process this image.",
      );
    }
  }

  const name: Record<string, string> = {
    "image-crop": "Image Cropper",
    "image-resize": "Image Resizer",
    "image-rotate": "Image Rotator",
    "color-picker": "Image Color Palette",
    "favicon-generator": "Favicon Generator",
    "exif-viewer": "EXIF Viewer / Remover",
    "meme-maker": "Meme Maker",
  };

  return (
    <section className="image-tool-workbench">
      <h2 className="text-lg font-semibold">{name[slug] ?? "Image tool"}</h2>
      <p className="mt-1 text-sm text-muted">
        Images stay in this browser. Maximum input: 25 MB and 40 megapixels.
      </p>
      <label className="mt-5 block text-sm font-semibold">
        Choose an image
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={chooseFile}
          className="mt-2 block w-full text-sm"
        />
      </label>
      {slug === "image-crop" && (
        <label className="mt-4 block text-sm font-semibold">
          Aspect ratio
          <input
            value={aspect}
            onChange={(event) => setAspect(event.target.value)}
            className="mt-2 block w-full rounded-xl border border-line-strong bg-transparent px-3 py-2 "
          />
        </label>
      )}
      {slug === "image-resize" && (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <label className="text-sm font-semibold">
            Maximum width
            <input
              type="number"
              min="1"
              max="4096"
              value={width}
              onChange={(event) => setWidth(event.target.value)}
              className="mt-2 block w-full rounded-xl border border-line-strong bg-transparent px-3 py-2 "
            />
          </label>
          <label className="text-sm font-semibold">
            Maximum height
            <input
              type="number"
              min="1"
              max="4096"
              value={height}
              onChange={(event) => setHeight(event.target.value)}
              className="mt-2 block w-full rounded-xl border border-line-strong bg-transparent px-3 py-2 "
            />
          </label>
        </div>
      )}
      {slug === "image-rotate" && (
        <label className="mt-4 block text-sm font-semibold">
          Rotation
          <select
            value={rotation}
            onChange={(event) => setRotation(event.target.value)}
            className="mt-2 block rounded-xl border border-line-strong bg-transparent px-3 py-2 "
          >
            <option value="90">90° clockwise</option>
            <option value="180">180°</option>
            <option value="270">270° clockwise</option>
          </select>
        </label>
      )}
      {slug === "meme-maker" && (
        <div className="mt-4 grid gap-3">
          <input
            value={topText}
            onChange={(event) => setTopText(event.target.value)}
            maxLength={100}
            placeholder="Top caption"
            aria-label="Top caption"
            className="rounded-xl border border-line-strong bg-transparent px-3 py-2 "
          />
          <input
            value={bottomText}
            onChange={(event) => setBottomText(event.target.value)}
            maxLength={100}
            placeholder="Bottom caption"
            aria-label="Bottom caption"
            className="rounded-xl border border-line-strong bg-transparent px-3 py-2 "
          />
        </div>
      )}
      {slug === "exif-viewer" && (
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={() => setExifAction("view")}
            className={`rounded-lg px-3 py-2 text-sm ${exifAction === "view" ? "bg-accent-soft text-accent" : "bg-subtle "}`}
          >
            View metadata
          </button>
          <button
            type="button"
            onClick={() => setExifAction("remove")}
            className={`rounded-lg px-3 py-2 text-sm ${exifAction === "remove" ? "bg-accent-soft text-accent" : "bg-subtle "}`}
          >
            Remove metadata
          </button>
        </div>
      )}
      {sourceUrl && (
        <img
          src={sourceUrl}
          alt="Selected image preview"
          className="mt-5 max-h-80 max-w-full rounded-xl object-contain"
        />
      )}
      <button
        type="button"
        disabled={!file}
        onClick={() => void process()}
        className="mt-5 rounded-xl bg-accent px-5 py-3 font-semibold text-white disabled:opacity-50"
      >
        {slug === "exif-viewer"
          ? exifAction === "view"
            ? "View EXIF metadata"
            : "Re-encode without metadata"
          : slug === "color-picker"
            ? "Extract palette"
            : slug === "favicon-generator"
              ? "Create favicon"
              : "Process image"}
      </button>
      {error && (
        <p role="alert" className="mt-4 text-sm text-red-600">
          {error}
        </p>
      )}
      {message && (
        <pre
          role="status"
          className="mt-4 whitespace-pre-wrap rounded-xl bg-canvas p-3 text-sm "
        >
          {message}
        </pre>
      )}
      {resultUrl && (
        <div className="mt-5">
          <img
            src={resultUrl}
            alt="Processed image result"
            className="max-h-96 max-w-full rounded-xl object-contain"
          />
          <a
            href={resultUrl}
            download={`${slug}-${file?.name.replace(/\.[^.]+$/u, "") ?? "image"}.${slug === "favicon-generator" ? "png" : "png"}`}
            className="mt-3 inline-block text-sm font-semibold text-accent "
          >
            Download processed image
          </a>
        </div>
      )}
    </section>
  );
}
