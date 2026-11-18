"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { DatasetSummary } from "@/lib/types";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import Badge from "@/components/ui/Badge";
import DepthMeter from "@/components/ui/DepthMeter";
import { formatBytes } from "@/components/ui/FileDrop";

const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : "None yet");

/**
 * What this hospital holds on the server: how many images, how much disk,
 * which formats and how close it is to the upload quota. Reloads whenever
 * `refreshKey` changes, so an upload or an erase shows up straight away.
 */
export default function StorageSummary({ refreshKey }: { refreshKey: number }) {
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<DatasetSummary>("/api/datasets/summary", { signal: controller.signal })
      .then((s) => {
        setSummary(s);
        setFailed(false);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [refreshKey]);

  const facts = summary
    ? [
        { label: "Images", value: summary.images.toLocaleString() },
        { label: "Disk used", value: formatBytes(summary.total_bytes) },
        { label: "Newest upload", value: when(summary.newest_upload) },
      ]
    : [];

  return (
    <Panel aria-labelledby="storage-title">
      <PanelHeader
        id="storage-title"
        title="Storage"
        description="What this node holds on the server. Pixels are never sent back, and photo metadata is removed on upload."
      />
      <PanelBody>
        {failed ? (
          <p className="text-[13px] text-ink-2">The storage summary could not be loaded.</p>
        ) : summary === null ? (
          <div className="space-y-3" aria-busy="true" aria-label="Loading storage">
            <div className="skeleton h-12 w-full" />
            <div className="skeleton h-3 w-2/3" />
          </div>
        ) : (
          <div className="space-y-5">
            <dl className="grid gap-4 sm:grid-cols-3">
              {facts.map((f) => (
                <div key={f.label} className="min-w-0">
                  <dt className="label-mono text-ink-3">{f.label}</dt>
                  <dd className="mt-1.5 truncate font-mono text-sm text-ink tabular">{f.value}</dd>
                </div>
              ))}
            </dl>

            <div>
              <div className="mb-2 flex items-baseline justify-between gap-4 text-[13px]">
                <span className="text-ink-2">Image quota</span>
                <span className="font-mono text-xs text-ink-3 tabular">
                  {summary.images.toLocaleString()} of {summary.quota.toLocaleString()}
                </span>
              </div>
              <DepthMeter value={summary.quota_used} label="Image quota used" />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="label-mono mr-1 text-ink-3">Formats</span>
              {Object.keys(summary.formats).length === 0 ? (
                <span className="text-[13px] text-ink-3">Nothing stored yet</span>
              ) : (
                Object.entries(summary.formats).map(([format, count]) => (
                  <Badge key={format}>
                    {format.toUpperCase()} · {count.toLocaleString()}
                  </Badge>
                ))
              )}
            </div>
          </div>
        )}
      </PanelBody>
    </Panel>
  );
}
