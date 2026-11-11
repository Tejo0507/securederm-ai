"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";
import type { BatchPredictionResponse, PredictionResult } from "@/lib/types";
import SectionHeader from "@/components/dashboard/SectionHeader";
import ModelInfoBanner from "@/components/dashboard/ModelInfoBanner";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import FileDrop from "@/components/ui/FileDrop";
import Notice from "@/components/ui/Notice";
import { IconAlert, IconCheck, IconScan } from "@/components/ui/icons";

const BATCH_MAX_IMAGES = 10; // mirrors MAX_BATCH_IMAGES in the backend
const BATCH_MAX_BYTES = 24 * 1024 * 1024; // just under the backend's 25 MB request cap

const pct = (n: number, digits = 1) => `${(n * 100).toFixed(digits)}%`;

export default function PredictTab() {
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [predicting, setPredicting] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [batch, setBatch] = useState<BatchPredictionResponse | null>(null);
  // Names are kept client-side only, to label the rows of a batch result.
  const [batchNames, setBatchNames] = useState<string[]>([]);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Release the last preview's blob URL when leaving the tab.
  const previewRef = useRef<string | null>(null);
  previewRef.current = preview;
  useEffect(() => {
    return () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    };
  }, []);

  function handleFiles(next: File[]) {
    setFiles(next);
    setResult(null);
    setBatch(null);
    setError("");
    if (preview) URL.revokeObjectURL(preview);
    // A preview only makes sense for a single image.
    setPreview(next.length === 1 ? URL.createObjectURL(next[0]) : null);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const chosen = Array.from(fileInputRef.current?.files ?? []);
    if (chosen.length === 0) {
      setError("Please select a wound image first.");
      return;
    }
    if (chosen.length > BATCH_MAX_IMAGES) {
      setError(`Select at most ${BATCH_MAX_IMAGES} images at a time.`);
      return;
    }
    if (chosen.reduce((sum, f) => sum + f.size, 0) > BATCH_MAX_BYTES) {
      setError("These images are too large to send together (24 MB limit). Select fewer.");
      return;
    }

    setPredicting(true);
    setError("");
    setResult(null);
    setBatch(null);

    const fd = new FormData();
    try {
      if (chosen.length === 1) {
        fd.append("file", chosen[0]);
        setResult(await apiFetch<PredictionResult>("/api/predict", { method: "POST", body: fd }));
      } else {
        chosen.forEach((f) => fd.append("files", f));
        setBatchNames(chosen.map((f) => f.name));
        setBatch(
          await apiFetch<BatchPredictionResponse>("/api/predict/batch", {
            method: "POST",
            body: fd,
          }),
        );
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Prediction failed. Is a trained model available?");
    } finally {
      setPredicting(false);
    }
  }

  const sortedProbabilities = result
    ? Object.entries(result.class_probabilities).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Diagnose"
        description="Classify a wound photo with the current global model. Only the result is saved to your history, never the image."
      />

      <ModelInfoBanner />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Panel as="form" onSubmit={handleSubmit} aria-labelledby="predict-input-title">
          <PanelHeader
            id="predict-input-title"
            title="Image"
            description={`One image for a detailed result, or up to ${BATCH_MAX_IMAGES} to classify together.`}
          />
          <PanelBody className="space-y-4">
            {preview ? (
              <div className="relative overflow-hidden rounded-lg border border-line bg-[repeating-conic-gradient(rgb(var(--sunken))_0%_25%,rgb(var(--surface))_0%_50%)] [background-size:16px_16px]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={preview} alt="Selected wound" className="mx-auto max-h-72 w-full object-contain" />
                {predicting && (
                  <div className="absolute inset-0 overflow-hidden" aria-hidden="true">
                    <div className="absolute inset-x-0 h-16 animate-[scan_1.6s_ease-in-out_infinite] bg-gradient-to-b from-transparent via-accent/25 to-transparent" />
                  </div>
                )}
              </div>
            ) : null}
            <FileDrop
              ref={fileInputRef}
              id="predict-files"
              accept="image/*"
              multiple
              aria-label={`Wound images (up to ${BATCH_MAX_IMAGES})`}
              title={files.length ? "Change images" : "Choose wound images"}
              hint={`Up to ${BATCH_MAX_IMAGES} images, 24 MB in total`}
              files={files}
              onFiles={handleFiles}
              disabled={predicting}
            />
            {error && (
              <Notice tone="danger" role="alert">
                {error}
              </Notice>
            )}
            <Button type="submit" size="lg" loading={predicting} disabled={files.length === 0} className="w-full">
              {!predicting && <IconScan size={16} />}
              {predicting ? "Analyzing..." : files.length > 1 ? `Analyze ${files.length} images` : "Analyze"}
            </Button>
          </PanelBody>
        </Panel>

        <Panel aria-labelledby="predict-result-title" aria-live="polite" aria-busy={predicting}>
          <PanelHeader id="predict-result-title" title="Result" />
          <PanelBody>
            {predicting ? (
              <div className="space-y-4" aria-label="Analyzing">
                <div className="skeleton h-24 w-full" />
                <div className="skeleton h-4 w-1/2" />
                <div className="skeleton h-4 w-2/3" />
                <div className="skeleton h-4 w-1/3" />
              </div>
            ) : batch ? (
              <BatchResult batch={batch} names={batchNames} />
            ) : result ? (
              <SingleResult result={result} probabilities={sortedProbabilities} />
            ) : (
              <div className="flex flex-col items-center rounded border border-dashed border-line-strong bg-canvas/60 px-6 py-14 text-center">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-surface text-ink-3 shadow-raise">
                  <IconScan size={18} />
                </span>
                <p className="mt-3 text-sm font-medium text-ink">No image analyzed yet</p>
                <p className="mt-1 max-w-xs text-[13px] leading-relaxed text-ink-2">
                  Choose an image and select Analyze. The most likely diagnoses and class probabilities
                  will appear here.
                </p>
              </div>
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}

function SingleResult({
  result,
  probabilities,
}: {
  result: PredictionResult;
  probabilities: [string, number][];
}) {
  const unknown = result.is_unknown;
  return (
    <div className="space-y-6">
      <div
        className={`rounded-lg border p-5 ${
          unknown ? "border-warn/30 bg-warn-soft" : "border-accent/25 bg-accent-soft"
        }`}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className={`label-mono ${unknown ? "text-warn-ink" : "text-accent-ink"}`}>
              {unknown ? "Refer to a clinician" : "Most likely"}
            </p>
            <p className="mt-1.5 text-xl font-semibold tracking-[-0.02em] text-ink sm:text-2xl">
              {unknown ? "Unrecognized pattern" : result.predicted_class}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="label-mono text-ink-3">Confidence</p>
            <p className="mt-1.5 font-mono text-xl font-medium text-ink tabular sm:text-2xl">{pct(result.confidence)}</p>
          </div>
        </div>
        <p className={`mt-3 flex items-start gap-2 text-[13px] leading-relaxed ${unknown ? "text-warn-ink" : "text-accent-ink"}`}>
          {unknown ? <IconAlert size={15} className="mt-0.5 shrink-0" /> : <IconCheck size={15} className="mt-0.5 shrink-0" />}
          {result.message}
        </p>
        {result.model_id && (
          <p className="mt-3 border-t border-ink/10 pt-3 text-xs text-ink-2">
            Answered by <span className="font-mono">{result.model_id}</span>
          </p>
        )}
      </div>

      {result.top_predictions && result.top_predictions.length > 0 && (
        <div>
          <div className="flex items-baseline justify-between">
            <h3 className="label-mono text-ink-3">Most likely diagnoses</h3>
            {typeof result.uncertainty === "number" && (
              <span className="text-xs text-ink-3">
                Model uncertainty <span className="font-mono text-ink-2 tabular">{pct(result.uncertainty, 0)}</span>
              </span>
            )}
          </div>
          <ol className="mt-2 divide-y divide-line rounded border border-line">
            {result.top_predictions.map((p, i) => (
              <li key={p.label} className="flex items-center justify-between gap-4 px-3.5 py-2.5 text-sm">
                <span className="flex min-w-0 items-center gap-3">
                  <span className="font-mono text-xs text-ink-3">{i + 1}</span>
                  <span className="truncate text-ink">{p.label}</span>
                </span>
                <span className="font-mono text-[13px] text-ink-2 tabular">{pct(p.probability)}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div>
        <h3 className="label-mono text-ink-3">Class probabilities</h3>
        <ul className="mt-3 space-y-2.5">
          {probabilities.map(([name, prob], i) => (
            <li key={name}>
              <div className="mb-1 flex justify-between gap-4 text-[13px]">
                <span className={i === 0 ? "font-medium text-ink" : "text-ink-2"}>{name}</span>
                <span className="font-mono text-xs text-ink-2 tabular">{pct(prob)}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-sunken">
                <div
                  className={`h-full rounded-full transition-[width] duration-500 ease-out ${i === 0 ? "bg-accent" : "bg-ink-3/50"}`}
                  style={{ width: `${prob * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function BatchResult({ batch, names }: { batch: BatchPredictionResponse; names: string[] }) {
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <Badge tone="success" dot>
          {batch.count} classified
        </Badge>
        {batch.failed > 0 && (
          <Badge tone="danger" dot>
            {batch.failed} could not be read
          </Badge>
        )}
      </div>
      <ul className="mt-4 divide-y divide-line rounded border border-line">
        {batch.results.map((slot) => (
          <li key={slot.index} className="flex flex-col gap-1.5 px-3.5 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
            <span className="min-w-0 truncate text-[13px] text-ink-2">
              {names[slot.index] ?? `Image ${slot.index + 1}`}
            </span>
            {slot.error !== undefined ? (
              <span className="text-[13px] text-danger-ink sm:text-right">{slot.error}</span>
            ) : slot.is_unknown ? (
              <span className="flex shrink-0 items-center gap-2">
                <Badge tone="warning">Refer</Badge>
                <span className="font-mono text-xs text-ink-3 tabular">{pct(slot.confidence, 0)}</span>
              </span>
            ) : (
              <span className="flex shrink-0 items-center gap-2">
                <span className="text-sm font-medium text-ink">{slot.predicted_class}</span>
                <span className="font-mono text-xs text-ink-3 tabular">{pct(slot.confidence, 0)}</span>
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
