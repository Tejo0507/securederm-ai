"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import type { ModelInfo } from "@/lib/types";
import Button from "@/components/ui/Button";
import Notice from "@/components/ui/Notice";
import { formatBytes } from "@/components/ui/FileDrop";
import { IconChip } from "@/components/ui/icons";

/** Which model will answer, so a result can be traced to a model version. */
export default function ModelInfoBanner() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    apiFetch<ModelInfo>("/api/model/info", { signal: controller.signal })
      .then(setInfo)
      .catch((err: unknown) => {
        if (controller.signal.aborted) return; // unmounted or retried
        setError(err instanceof ApiError ? err.message : "Could not load model details.");
      });
    return () => controller.abort();
  }, [attempt]);

  if (error) {
    return (
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Notice tone="warning" role="alert" title="Model details are unavailable" className="flex-1">
          {error} You can still try a diagnosis; the server reports which model answered.
        </Notice>
        <Button variant="secondary" size="sm" onClick={() => setAttempt((a) => a + 1)} className="self-start sm:self-auto">
          Try again
        </Button>
      </div>
    );
  }

  if (!info) return <div className="skeleton h-[58px] w-full rounded-lg" aria-hidden="true" />;

  if (!info.available) {
    return (
      <Notice tone="warning" title="No trained model is deployed yet">
        Diagnoses are unavailable until federated training has produced a model. Start a run from the
        Training section.
      </Notice>
    );
  }

  const facts: { label: string; value: string }[] = [
    ...(info.updated_at ? [{ label: "Updated", value: new Date(info.updated_at).toLocaleString() }] : []),
    ...(info.size_bytes != null ? [{ label: "Size", value: formatBytes(info.size_bytes) }] : []),
    { label: "Classes", value: String(info.classes.length) },
    { label: "Refers below", value: `${(info.unknown_threshold * 100).toFixed(0)}% confidence` },
  ];

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface px-4 py-3 shadow-raise sm:flex-row sm:items-center sm:gap-6">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded border border-accent/25 bg-accent-soft text-accent-ink">
          <IconChip size={16} />
        </span>
        <div className="min-w-0">
          <p className="label-mono text-ink-3">Active model</p>
          <p className="truncate font-mono text-[13px] font-medium text-ink">{info.model_id}</p>
        </div>
      </div>
      <dl className="flex flex-wrap gap-x-6 gap-y-2 sm:ml-auto sm:justify-end">
        {facts.map((f) => (
          <div key={f.label} className="min-w-0">
            <dt className="text-2xs text-ink-3">{f.label}</dt>
            <dd className="text-[13px] text-ink tabular">{f.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
