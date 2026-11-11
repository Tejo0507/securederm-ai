"use client";

import { useEffect, useState } from "react";
import { apiDownload, apiFetch } from "@/lib/api";
import HistoryTimeline from "@/components/dashboard/HistoryTimeline";
import SectionHeader from "@/components/dashboard/SectionHeader";
import { useConfirm } from "@/components/ConfirmProvider";
import { Panel, PanelBody, PanelHeader, StatStrip } from "@/components/ui/Panel";
import Button from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import Notice from "@/components/ui/Notice";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import {
  IconChevronLeft,
  IconChevronRight,
  IconDownload,
  IconHistory,
  IconTrash,
} from "@/components/ui/icons";
import type { HistoryPage, HistorySummary } from "@/lib/types";

const PAGE_SIZE = 20;

type UnknownFilter = "all" | "unknown" | "recognized";

/** The API stores naive UTC timestamps; without a zone `Date` would read them as local time. */
function formatUtc(ts: string | null): string {
  if (!ts) return "Not recorded";
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(ts);
  return new Date(hasZone ? ts : `${ts}Z`).toLocaleString();
}

/** The day after a YYYY-MM-DD date, because the API's `until` is exclusive. */
function nextDay(date: string): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
}

function filterParams(
  label: string,
  unknown: UnknownFilter,
  from: string,
  to: string,
): URLSearchParams {
  const params = new URLSearchParams();
  if (label) params.set("label", label);
  if (unknown !== "all") params.set("unknown", String(unknown === "unknown"));
  // Dates are UTC days, matching how the API stores timestamps; `to` is
  // inclusive in the UI, so the exclusive API bound is the following day.
  if (from) params.set("since", from);
  if (to) params.set("until", nextDay(to));
  return params;
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export default function HistoryTab() {
  const confirm = useConfirm();
  const [summary, setSummary] = useState<HistorySummary | null>(null);
  const [page, setPage] = useState<HistoryPage | null>(null);
  const [label, setLabel] = useState("");
  const [unknown, setUnknown] = useState<UnknownFilter>("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<HistorySummary>("/api/predictions/summary", { signal: controller.signal })
      .then(setSummary)
      .catch(() => {});
    return () => controller.abort();
  }, [reloadKey]);

  // A class with no entries left (say its last one was just deleted) must not
  // stay selected: the dropdown would fall back to "All classes" while the table
  // kept filtering on the vanished class and claimed nothing matched.
  useEffect(() => {
    if (label && summary && !(label in summary.by_class)) {
      setLabel("");
      setOffset(0);
    }
  }, [label, summary]);

  const rangeInvalid = from !== "" && to !== "" && from > to;

  useEffect(() => {
    if (rangeInvalid) return;
    const controller = new AbortController();
    const params = filterParams(label, unknown, from, to);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    setLoading(true);
    setError("");
    apiFetch<HistoryPage>(`/api/predictions?${params}`, { signal: controller.signal })
      .then(setPage)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(err, "Could not load history."));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [label, unknown, from, to, rangeInvalid, offset, reloadKey]);

  async function deleteEntry(id: number) {
    const ok = await confirm({
      title: "Delete this entry?",
      message: "It is removed from your prediction history. This cannot be undone.",
      confirmLabel: "Delete entry",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    setError("");
    try {
      await apiFetch(`/api/predictions/${id}`, { method: "DELETE" });
      // Step back a page if that was the last row of the current one.
      if (items.length === 1 && offset > 0) setOffset(Math.max(0, offset - PAGE_SIZE));
      setReloadKey((k) => k + 1);
    } catch (err: unknown) {
      setError(errorMessage(err, "Could not delete that entry."));
    } finally {
      setBusy(false);
    }
  }

  async function exportCsv() {
    setBusy(true);
    setError("");
    try {
      const query = filterParams(label, unknown, from, to).toString();
      await apiDownload(
        `/api/predictions/export${query ? `?${query}` : ""}`,
        "prediction-history.csv",
      );
    } catch (err: unknown) {
      setError(errorMessage(err, "Could not export history."));
    } finally {
      setBusy(false);
    }
  }

  async function eraseHistory() {
    const ok = await confirm({
      title: "Erase your entire history?",
      message:
        "Every recorded diagnosis result is permanently deleted from your account. This cannot be undone.",
      confirmLabel: "Erase history",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    setError("");
    try {
      await apiFetch("/api/predictions", { method: "DELETE" });
      setLabel("");
      setUnknown("all");
      setFrom("");
      setTo("");
      setOffset(0);
      setReloadKey((k) => k + 1);
    } catch (err: unknown) {
      setError(errorMessage(err, "Could not erase history."));
    } finally {
      setBusy(false);
    }
  }

  // With an inverted range no request is made, so don't keep showing the last
  // response's rows as if they matched it.
  const total = rangeInvalid ? 0 : (page?.total ?? 0);
  const items = rangeInvalid ? [] : (page?.items ?? []);
  const classes = summary ? Object.keys(summary.by_class) : [];
  const hasAnyHistory = (summary?.total ?? 0) > 0;
  const lastOffset = Math.max(0, Math.floor((total - 1) / PAGE_SIZE) * PAGE_SIZE);

  const cards = [
    { label: "Diagnoses", value: String(summary?.total ?? 0) },
    {
      label: "Flagged unknown",
      value: summary ? `${(summary.unknown_rate * 100).toFixed(0)}%` : "n/a",
    },
    {
      label: "Avg confidence",
      value:
        summary?.average_confidence != null
          ? `${(summary.average_confidence * 100).toFixed(0)}%`
          : "n/a",
    },
    { label: "Models used", value: String(summary?.by_model.length ?? 0) },
  ];

  const maxClassCount = Math.max(1, ...Object.values(summary?.by_class ?? {}));
  const showClasses = !!summary && classes.length > 0;

  return (
    <div className="animate-fade-up">
      <SectionHeader
        title="Diagnosis history"
        description="Only each result is kept, never the image. The model ID identifies the exact model version that answered."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={exportCsv}
              disabled={busy || !hasAnyHistory || rangeInvalid}
            >
              <IconDownload size={15} />
              Export CSV
            </Button>
            <Button variant="danger-quiet" size="sm" onClick={eraseHistory} disabled={busy || !hasAnyHistory}>
              <IconTrash size={15} />
              Erase history
            </Button>
          </>
        }
      />

      <div className="space-y-6">
        <StatStrip stats={cards} />

        {(hasAnyHistory || showClasses) && (
          <div className={`grid gap-6 ${hasAnyHistory && showClasses ? "xl:grid-cols-[1.6fr_1fr]" : ""}`}>
            {hasAnyHistory && <HistoryTimeline reloadKey={reloadKey} />}

            {showClasses && (
              <Panel className="h-full">
                <PanelHeader title="Diagnoses by class" />
                <PanelBody>
                  <ul className="space-y-3">
                    {classes.map((name) => (
                      <li key={name}>
                        <div className="mb-1.5 flex justify-between gap-3 text-[13px]">
                          <span className="truncate text-ink">{name}</span>
                          <span className="font-mono text-xs text-ink-2 tabular">{summary.by_class[name]}</span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-sunken">
                          <div
                            className="h-full rounded-full bg-accent"
                            style={{ width: `${(summary.by_class[name] / maxClassCount) * 100}%` }}
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                </PanelBody>
              </Panel>
            )}
          </div>
        )}

        <Panel className="overflow-hidden">
          <PanelHeader title="Predictions" description={`${total} matching ${total === 1 ? "entry" : "entries"}`} />

          {/* filter toolbar */}
          <div className="mt-4 flex flex-wrap items-end gap-3 border-y border-line bg-canvas px-5 py-3 sm:px-6">
            <div className="w-full sm:w-44">
              <label className="label-mono mb-1 block text-ink-3" htmlFor="history-label">
                Class
              </label>
              <Select
                compact
                id="history-label"
                value={label}
                onChange={(e) => {
                  setLabel(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All classes</option>
                {classes.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="w-full sm:w-44">
              <label className="label-mono mb-1 block text-ink-3" htmlFor="history-unknown">
                Outcome
              </label>
              <Select
                compact
                id="history-unknown"
                value={unknown}
                onChange={(e) => {
                  setUnknown(e.target.value as UnknownFilter);
                  setOffset(0);
                }}
              >
                <option value="all">All outcomes</option>
                <option value="recognized">Recognized</option>
                <option value="unknown">Flagged unknown</option>
              </Select>
            </div>
            <div className="min-w-0 flex-1 sm:flex-none">
              <label className="label-mono mb-1 block text-ink-3" htmlFor="history-from">
                From (UTC)
              </label>
              <Input
                compact
                id="history-from"
                type="date"
                value={from}
                max={to || undefined}
                onChange={(e) => {
                  setFrom(e.target.value);
                  setOffset(0);
                }}
              />
            </div>
            <div className="min-w-0 flex-1 sm:flex-none">
              <label className="label-mono mb-1 block text-ink-3" htmlFor="history-to">
                To (UTC)
              </label>
              <Input
                compact
                id="history-to"
                type="date"
                value={to}
                min={from || undefined}
                onChange={(e) => {
                  setTo(e.target.value);
                  setOffset(0);
                }}
              />
            </div>
          </div>

          {(rangeInvalid || error) && (
            <div className="space-y-2 px-5 pt-4 sm:px-6">
              {rangeInvalid && (
                <Notice tone="warning" role="status">
                  The start date is after the end date, so nothing can match.
                </Notice>
              )}
              {error && (
                <Notice tone="danger" role="alert">
                  {error}
                </Notice>
              )}
            </div>
          )}

          {loading && !page ? (
            <div className="space-y-3 p-5 sm:p-6" aria-busy="true" aria-label="Loading history">
              {[0, 1, 2, 3, 4].map((i) => (
                <div key={i} className="skeleton h-8 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="p-5 sm:p-6">
              <EmptyState icon={<IconHistory size={18} />} title={hasAnyHistory ? "No matches" : "No diagnoses yet"}>
                {hasAnyHistory
                  ? "No predictions match these filters."
                  : "No diagnoses yet. Results from the Predict tab will appear here."}
              </EmptyState>
            </div>
          ) : (
            <div className="relative overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-line bg-canvas text-left">
                    <th className="label-mono px-5 py-2.5 font-medium text-ink-3 sm:pl-6">When</th>
                    <th className="label-mono px-3 py-2.5 font-medium text-ink-3">Class</th>
                    <th className="label-mono px-3 py-2.5 text-right font-medium text-ink-3">Confidence</th>
                    <th className="label-mono px-3 py-2.5 text-right font-medium text-ink-3">Uncertainty</th>
                    <th className="label-mono px-3 py-2.5 font-medium text-ink-3">Outcome</th>
                    <th className="label-mono px-3 py-2.5 font-medium text-ink-3">Model</th>
                    <th className="px-5 py-2.5 sm:pr-6">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className={`transition-opacity ${loading ? "opacity-50" : ""}`}>
                  {items.map((row) => (
                    <tr key={row.id} className="border-b border-line last:border-b-0 hover:bg-canvas/70">
                      <td className="whitespace-nowrap px-5 py-2.5 text-ink-2 tabular sm:pl-6">
                        {formatUtc(row.created_at)}
                      </td>
                      <td className="px-3 py-2.5 font-medium text-ink">{row.predicted_class}</td>
                      <td className="px-3 py-2.5 text-right text-ink tabular">
                        {(row.confidence * 100).toFixed(1)}%
                      </td>
                      <td className="px-3 py-2.5 text-right text-ink-2 tabular">
                        {(row.uncertainty * 100).toFixed(0)}%
                      </td>
                      <td className="px-3 py-2.5">
                        {row.is_unknown ? (
                          <Badge tone="warning" dot>
                            Refer
                          </Badge>
                        ) : (
                          <Badge tone="success" dot>
                            Recognized
                          </Badge>
                        )}
                      </td>
                      <td className="px-3 py-2.5 font-mono text-xs text-ink-3">{row.model_id || "Not recorded"}</td>
                      <td className="px-5 py-1.5 text-right sm:pr-6">
                        <button
                          type="button"
                          onClick={() => deleteEntry(row.id)}
                          disabled={busy}
                          aria-label={`Delete the ${row.predicted_class} entry from ${formatUtc(row.created_at)}`}
                          className="inline-flex h-8 w-8 items-center justify-center rounded text-ink-3 transition-colors hover:bg-danger-soft hover:text-danger-ink disabled:opacity-40"
                        >
                          <IconTrash size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {total > PAGE_SIZE && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3 text-[13px] text-ink-2 sm:px-6">
              <span className="tabular">
                {offset + 1} to {Math.min(offset + PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  disabled={offset === 0 || loading}
                >
                  <IconChevronLeft size={14} />
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setOffset(Math.min(lastOffset, offset + PAGE_SIZE))}
                  disabled={offset >= lastOffset || loading}
                >
                  Next
                  <IconChevronRight size={14} />
                </Button>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
