"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiFetch } from "@/lib/api";
import type { HistoryTimeline as Timeline } from "@/lib/types";

const RANGES = [7, 30, 90] as const;

/** Diagnoses per day, split into recognized and flagged-unknown. Reloads when `reloadKey` changes. */
export default function HistoryTimeline({ reloadKey }: { reloadKey: number }) {
  const [days, setDays] = useState<(typeof RANGES)[number]>(30);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setFailed(false);
    apiFetch<Timeline>(`/api/predictions/timeline?days=${days}`, { signal: controller.signal })
      .then(setTimeline)
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [days, reloadKey]);

  const data = useMemo(
    () =>
      (timeline?.series ?? []).map((p) => ({
        day: p.date.slice(5), // MM-DD keeps the axis readable
        date: p.date,
        Recognized: p.total - p.unknown,
        "Flagged unknown": p.unknown,
      })),
    [timeline],
  );
  const total = (timeline?.series ?? []).reduce((sum, p) => sum + p.total, 0);

  return (
    <div className="glass rounded-xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="font-semibold">Activity</h3>
          <p className="text-xs text-zinc-500 mt-1">
            {timeline ? `${total} diagnoses in the last ${days} days (UTC days)` : "Loading…"}
          </p>
        </div>
        <div className="flex gap-1" role="group" aria-label="Time range">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setDays(r)}
              aria-pressed={days === r}
              className={`px-3 py-1 text-xs rounded-lg border transition-colors ${
                days === r
                  ? "bg-indigo-600/30 border-indigo-500/40 text-indigo-200"
                  : "bg-white/5 border-white/10 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {r} days
            </button>
          ))}
        </div>
      </div>

      {failed ? (
        <p className="text-sm text-zinc-500">The activity chart is unavailable right now.</p>
      ) : timeline && total === 0 ? (
        <p className="text-sm text-zinc-500">No diagnoses in this period.</p>
      ) : (
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis
                dataKey="day"
                tick={{ fill: "#71717a", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
                minTickGap={24}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: "#71717a", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
                contentStyle={{
                  background: "#18181b",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ""}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Recognized" stackId="a" fill="#6366f1" radius={[0, 0, 0, 0]} />
              <Bar dataKey="Flagged unknown" stackId="a" fill="#fbbf24" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
