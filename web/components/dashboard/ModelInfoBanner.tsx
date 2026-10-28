"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { ModelInfo } from "@/lib/types";

function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

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

  if (!info) return null;

  if (!info.available) {
    return (
      <div className="rounded-xl border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm text-amber-300">
        No trained model is deployed yet, so diagnoses are unavailable. Run federated
        training first.
      </div>
    );
  }

  return (
    <div className="glass rounded-xl px-4 py-3 text-xs text-zinc-400 flex flex-wrap gap-x-6 gap-y-1">
      <span>
        Model <span className="font-mono text-zinc-200">{info.model_id}</span>
      </span>
      {info.updated_at && <span>Updated {new Date(info.updated_at).toLocaleString()}</span>}
      {info.size_bytes != null && <span>{formatSize(info.size_bytes)}</span>}
      <span>{info.classes.length} classes</span>
      <span>
        Flags &ldquo;unknown&rdquo; below {(info.unknown_threshold * 100).toFixed(0)}% confidence
      </span>
    </div>
  );
}
