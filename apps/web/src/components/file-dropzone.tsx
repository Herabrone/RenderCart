"use client";
import { File, Upload, X } from "lucide-react";
import { useId, useRef, useState } from "react";

export function FileDropzone({
  files,
  accept,
  multiple,
  disabled,
  onChange,
}: {
  files: File[];
  accept: string;
  multiple: boolean;
  disabled?: boolean;
  onChange: (files: File[]) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  const hint = accept
    .split(",")
    .map((type) =>
      type.split("/").pop()?.replace("vnd.openxmlformats-officedocument.", ""),
    )
    .join(" · ");
  function select(next: File[]) {
    if (!disabled) onChange(multiple ? next : next.slice(0, 1));
  }
  return (
    <div>
      <div
        className={`upload-zone ${dragging ? "drag-active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={(e) => {
          if (
            !(e.relatedTarget instanceof Node) ||
            !e.currentTarget.contains(e.relatedTarget)
          )
            setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          select(Array.from(e.dataTransfer.files));
        }}
      >
        <Upload size={29} strokeWidth={1.5} />
        <label htmlFor={id}>
          <strong>
            {multiple ? "Drop your files here" : "Drop a file here"}
          </strong>
          <span className="text-xs text-muted">or choose from your device</span>
        </label>
        <input
          ref={input}
          id={id}
          aria-label={multiple ? "Choose files" : "Choose a file"}
          type="file"
          accept={accept}
          multiple={multiple}
          disabled={disabled}
          onChange={(e) => select(Array.from(e.target.files ?? []))}
        />
        <p>{hint}</p>
      </div>
      {files.length > 0 && (
        <ul className="upload-file-list" aria-label="Selected files">
          {files.map((file, index) => (
            <li className="upload-file-row" key={`${file.name}-${index}`}>
              <File size={17} />
              <span>{file.name}</span>
              <small>
                {file.size < 1024 * 1024
                  ? `${Math.ceil(file.size / 1024)} KB`
                  : `${(file.size / 1024 / 1024).toFixed(1)} MB`}
              </small>
              <button
                type="button"
                className="icon-button"
                disabled={disabled}
                aria-label={`Remove ${file.name}`}
                onClick={() => {
                  select(files.filter((_, i) => i !== index));
                  if (input.current) input.current.value = "";
                }}
              >
                <X size={15} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
