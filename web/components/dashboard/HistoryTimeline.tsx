"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiFetch } from "@/lib/api";
import { chart } from "@/lib/chart";
import type { HistoryTimeline as Timeline } from "@/lib/types";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import EmptyState from "@/components/ui/EmptyState";
import { IconPulse } from "@/components/ui/icons";

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
    <Panel className="h-full">
      <PanelHeader
        title="Activity"
        description={timeline ? `${total} diagnoses in the last ${days} days (UTC days)` : "Loading..."}
        actions={
          <div
            className="inline-flex rounded border border-line-strong bg-canvas p-0.5"
            role="group"
            aria-label="Time range"
          >
            {RANGES.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setDays(r)}
                aria-pressed={days === r}
                className={`h-7 rounded-[4px] px-2.5 text-xs font-medium tabular transition-colors ${
                  days === r ? "bg-surface text-ink shadow-raise" : "text-ink-2 hover:text-ink"
                }`}
              >
                {r} days
              </button>
            ))}
          </div>
        }
      />
      <PanelBody>
        {failed ? (
          <EmptyState icon={<IconPulse size={18} />} title="Chart unavailable">
            The activity chart is unavailable right now.
          </EmptyState>
        ) : timeline && total === 0 ? (
          <EmptyState icon={<IconPulse size={18} />} title="No diagnoses in this period" />
        ) : !timeline ? (
          <div className="skeleton h-56 w-full" aria-hidden="true" />
        ) : (
          <>
            <div className="mb-3 flex gap-4 text-xs text-ink-2">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-accent" />
                Recognized
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-warn" />
                Flagged unknown
              </span>
            </div>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke={chart.grid} vertical={false} />
                  <XAxis
                    dataKey="day"
                    tick={chart.axisTick}
                    tickLine={false}
                    axisLine={false}
                    interval="preserveStartEnd"
                    minTickGap={24}
                  />
                  <YAxis allowDecimals={false} tick={chart.axisTick} tickLine={false} axisLine={false} />
                  <Tooltip
                    {...chart.tooltip}
                    cursor={chart.barCursor}
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ""}
                  />
                  <Bar dataKey="Recognized" stackId="a" fill={chart.series} radius={[0, 0, 0, 0]} />
                  <Bar dataKey="Flagged unknown" stackId="a" fill={chart.seriesAlt} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </PanelBody>
    </Panel>
  );
}
