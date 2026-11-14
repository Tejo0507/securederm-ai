"use client";

import { forwardRef, useState, type DragEvent, type ReactNode } from "react";
import { IconImage, IconUpload } from "@/components/ui/icons";

export function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/**
 * A file picker that is also a drop target. The real <input type="file"> stays
 * in the form (visually hidden but focusable), so forms that read it directly
 * keep working; dropped files are written into that same input.
 */
const FileDrop = forwardRef<
  HTMLInputElement,
  {
    id: string;
    accept?: string;
    multiple?: boolean;
    title: ReactNode;
    hint?: ReactNode;
    /** Files currently chosen, for the summary line. */
    files: File[];
    onFiles: (files: File[]) => void;
    disabled?: boolean;
    "aria-label"?: string;
  }
>(function FileDrop({ id, accept, multiple, title, hint, files, onFiles, disabled, ...rest }, ref) {
  const [over, setOver] = useState(false);

  function onDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setOver(false);
    if (disabled) return;
    const input = (e.currentTarget.querySelector("input[type=file]") as HTMLInputElement) ?? null;
    const dropped = e.dataTransfer.files;
    if (!input || !dropped.length) return;
    // Respect `multiple` and `accept` the way the native picker would.
    const dt = new DataTransfer();
    Array.from(dropped)
      .filter((f) => accept !== "image/*" || f.type.startsWith("image/"))
      .slice(0, multiple ? undefined : 1)
      .forEach((f) => dt.items.add(f));
    input.files = dt.files;
    onFiles(Array.from(dt.files));
  }

  const total = files.reduce((s, f) => s + f.size, 0);

  return (
    <label
      htmlFor={id}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={`group relative flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-6 py-8 text-center shadow-[inset_0_2px_8px_rgb(var(--shadow)/0.07)] transition-[background-color,border-color,transform] duration-200 focus-within:border-accent focus-within:ring-[3px] focus-within:ring-accent/20 ${
        over ? "scale-[1.01] border-accent bg-accent-soft/60" : "border-line-strong bg-canvas hover:border-ink-3 hover:bg-sunken/60"
      } ${disabled ? "pointer-events-none opacity-60" : ""}`}
    >
      <input
        ref={ref}
        id={id}
        type="file"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        onChange={(e) => onFiles(Array.from(e.target.files ?? []))}
        className="sr-only"
        {...rest}
      />
      <span
        className={`flex h-10 w-10 items-center justify-center rounded-lg border bg-surface transition-[color,border-color,transform,box-shadow] duration-200 ${
          over ? "-translate-y-1.5 border-accent/50 text-accent shadow-lift" : "border-line text-ink-2 shadow-edge-neutral group-hover:-translate-y-0.5 group-hover:text-ink"
        }`}
      >
        {files.length > 0 ? <IconImage size={18} /> : <IconUpload size={18} />}
      </span>
      {files.length > 0 ? (
        <>
          <span className="mt-3 max-w-full truncate text-sm font-medium text-ink">
            {files.length === 1 ? files[0].name : `${files.length} images selected`}
          </span>
          <span className="mt-1 font-mono text-xs text-ink-3">
            {formatBytes(total)} · <span className="font-sans text-accent-ink underline-offset-4 group-hover:underline">change</span>
          </span>
        </>
      ) : (
        <>
          <span className="mt-3 text-sm text-ink">
            <span className="font-medium text-accent-ink underline-offset-4 group-hover:underline">{title}</span>{" "}
            <span className="text-ink-2">or drag and drop</span>
          </span>
          {hint && <span className="mt-1 text-xs text-ink-3">{hint}</span>}
        </>
      )}
    </label>
  );
});

export default FileDrop;
