"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { ModelInfo } from "@/lib/types";
import Notice from "@/components/ui/Notice";
import { formatBytes } from "@/components/ui/FileDrop";
import { IconChip } from "@/components/ui/icons";

/** Which model will answer, so a result can be traced to a model version. */
export default function ModelInfoBanner() {
  const [info, setInfo] = useState<ModelInfo | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<ModelInfo>("/api/model/info", { signal: controller.signal })
      .then(setInfo)
      .catch(() => {});
    return () => controller.abort();
  }, []);

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
