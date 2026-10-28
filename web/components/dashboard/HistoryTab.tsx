"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { apiDownload, apiFetch } from "@/lib/api";
import type { HistoryPage, HistorySummary } from "@/lib/types";

const PAGE_SIZE = 20;

type UnknownFilter = "all" | "unknown" | "recognized";

/** The API stores naive UTC timestamps; without a zone `Date` would read them as local time. */
function formatUtc(ts: string | null): string {
  if (!ts) return "—";
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(ts);
  return new Date(hasZone ? ts : `${ts}Z`).toLocaleString();
}

function filterParams(label: string, unknown: UnknownFilter): URLSearchParams {
  const params = new URLSearchParams();
  if (label) params.set("label", label);
  if (unknown !== "all") params.set("unknown", String(unknown === "unknown"));
  return params;
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export default function HistoryTab() {
  const [summary, setSummary] = useState<HistorySummary | null>(null);
  const [page, setPage] = useState<HistoryPage | null>(null);
  const [label, setLabel] = useState("");
  const [unknown, setUnknown] = useState<UnknownFilter>("all");
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

  useEffect(() => {
    const controller = new AbortController();
    const params = filterParams(label, unknown);
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
  }, [label, unknown, offset, reloadKey]);

  async function exportCsv() {
    setBusy(true);
    setError("");
    try {
      const query = filterParams(label, unknown).toString();
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
    if (!window.confirm("Erase your entire prediction history? This cannot be undone.")) return;
    setBusy(true);
    setError("");
    try {
      await apiFetch("/api/predictions", { method: "DELETE" });
      setLabel("");
      setUnknown("all");
      setOffset(0);
      setReloadKey((k) => k + 1);
    } catch (err: unknown) {
      setError(errorMessage(err, "Could not erase history."));
    } finally {
      setBusy(false);
    }
  }

  const total = page?.total ?? 0;
  const items = page?.items ?? [];
  const classes = summary ? Object.keys(summary.by_class) : [];
  const hasAnyHistory = (summary?.total ?? 0) > 0;
  const lastOffset = Math.max(0, Math.floor((total - 1) / PAGE_SIZE) * PAGE_SIZE);

  const cards = [
    { label: "Diagnoses", value: String(summary?.total ?? 0) },
    {
      label: "Flagged unknown",
      value: summary ? `${(summary.unknown_rate * 100).toFixed(0)}%` : "—",
    },
    {
      label: "Avg confidence",
      value:
        summary?.average_confidence != null
          ? `${(summary.average_confidence * 100).toFixed(0)}%`
          : "—",
    },
    { label: "Models used", value: String(summary?.by_model.length ?? 0) },
  ];

  const maxClassCount = Math.max(1, ...Object.values(summary?.by_class ?? {}));

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-8">
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="glass rounded-xl p-5">
            <div className="text-xs text-zinc-500 uppercase tracking-wider">{c.label}</div>
            <div className="mt-1 text-xl font-bold">{c.value}</div>
          </div>
        ))}
      </div>

      {summary && classes.length > 0 && (
        <div className="glass rounded-xl p-6">
          <h3 className="font-semibold mb-4">Diagnoses by class</h3>
          <div className="space-y-2">
            {classes.map((name) => (
              <div key={name}>
                <div className="flex justify-between text-xs text-zinc-400 mb-1">
                  <span>{name}</span>
                  <span>{summary.by_class[name]}</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 to-purple-400 rounded-full"
                    style={{ width: `${(summary.by_class[name] / maxClassCount) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="glass rounded-xl p-6">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-4">
          <div>
            <h3 className="font-semibold">Prediction history</h3>
            <p className="text-xs text-zinc-500 mt-1">
              Only the result is kept — never the image. Model ID identifies the exact model
              version that answered.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <label className="sr-only" htmlFor="history-label">
              Filter by class
            </label>
            <select
              id="history-label"
              value={label}
              onChange={(e) => {
                setLabel(e.target.value);
                setOffset(0);
              }}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-zinc-300"
            >
              <option value="">All classes</option>
              {classes.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <label className="sr-only" htmlFor="history-unknown">
              Filter by outcome
            </label>
            <select
              id="history-unknown"
              value={unknown}
              onChange={(e) => {
                setUnknown(e.target.value as UnknownFilter);
                setOffset(0);
              }}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-zinc-300"
            >
              <option value="all">All outcomes</option>
              <option value="recognized">Recognized</option>
              <option value="unknown">Flagged unknown</option>
            </select>
            <button
              onClick={exportCsv}
              disabled={busy || !hasAnyHistory}
              className="px-3 py-1.5 text-sm rounded-lg bg-indigo-600/20 border border-indigo-500/30 text-indigo-300 hover:bg-indigo-600/30 disabled:opacity-40 transition-colors"
            >
              Export CSV
            </button>
            <button
              onClick={eraseHistory}
              disabled={busy || !hasAnyHistory}
              className="px-3 py-1.5 text-sm rounded-lg bg-rose-600/10 border border-rose-500/30 text-rose-300 hover:bg-rose-600/20 disabled:opacity-40 transition-colors"
            >
              Erase history
            </button>
          </div>
        </div>

        {error && <p className="text-sm text-rose-400 mb-3">{error}</p>}

        {loading && !page ? (
          <p className="text-sm text-zinc-500">Loading…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-zinc-500">
            {hasAnyHistory
              ? "No predictions match these filters."
              : "No diagnoses yet. Results from the Predict tab will appear here."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-zinc-500 uppercase tracking-wider">
                  <th className="py-2 pr-4 font-medium">When</th>
                  <th className="py-2 pr-4 font-medium">Class</th>
                  <th className="py-2 pr-4 font-medium">Confidence</th>
                  <th className="py-2 pr-4 font-medium">Uncertainty</th>
                  <th className="py-2 pr-4 font-medium">Outcome</th>
                  <th className="py-2 font-medium">Model</th>
                </tr>
              </thead>
              <tbody className={loading ? "opacity-50" : ""}>
                {items.map((row) => (
                  <tr key={row.id} className="border-t border-white/5 text-zinc-300">
                    <td className="py-2 pr-4 whitespace-nowrap">{formatUtc(row.created_at)}</td>
                    <td className="py-2 pr-4">{row.predicted_class}</td>
                    <td className="py-2 pr-4">{(row.confidence * 100).toFixed(1)}%</td>
                    <td className="py-2 pr-4">{(row.uncertainty * 100).toFixed(0)}%</td>
                    <td className="py-2 pr-4">
                      {row.is_unknown ? (
                        <span className="text-amber-300">Unknown — refer</span>
                      ) : (
                        <span className="text-emerald-300">Recognized</span>
                      )}
                    </td>
                    <td className="py-2 font-mono text-xs text-zinc-500">
                      {row.model_id || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between mt-4 text-sm text-zinc-400">
            <span>
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0 || loading}
                className="px-3 py-1 rounded-lg bg-white/5 border border-white/10 disabled:opacity-40"
              >
                Previous
              </button>
              <button
                onClick={() => setOffset(Math.min(lastOffset, offset + PAGE_SIZE))}
                disabled={offset >= lastOffset || loading}
                className="px-3 py-1 rounded-lg bg-white/5 border border-white/10 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
