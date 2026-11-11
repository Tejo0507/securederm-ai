"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiFetch, ApiError } from "@/lib/api";
import { chart } from "@/lib/chart";
import { useConfirm } from "@/components/ConfirmProvider";
import SectionHeader from "@/components/dashboard/SectionHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import Notice from "@/components/ui/Notice";
import EmptyState from "@/components/ui/EmptyState";
import { IconPlay, IconPulse, IconStop } from "@/components/ui/icons";

interface Metric {
  round: number;
  avg_loss: number;
  nodes: number;
}

interface TrainingStatus {
  active: boolean;
  round: number;
  total_rounds: number;
  loss: number;
  logs: string[];
  metrics: Metric[];
}

function logTone(log: string): string {
  if (/complete/i.test(log)) return "text-ok-ink";
  if (log.includes("uploading") || log.includes("merging")) return "text-accent-ink";
  if (/error|fail/i.test(log)) return "text-danger-ink";
  return "text-ink-2";
}

export default function TrainingTab() {
  const confirm = useConfirm();
  const router = useRouter();
  const [status, setStatus] = useState<TrainingStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState("");
  const logsContainerRef = useRef<HTMLOListElement>(null);

  const poll = useCallback(() => {
    // No point polling (or waking the server every 1.5 s) for a hidden tab.
    if (document.hidden) return;
    apiFetch<TrainingStatus>("/api/training/status")
      .then(setStatus)
      .catch((err: unknown) => {
        // An expired session would otherwise be retried forever, silently.
        if (err instanceof ApiError && err.status === 401) {
          localStorage.removeItem("hospital");
          router.push("/login");
        }
      });
  }, [router]);

  useEffect(() => {
    poll();
    const interval = setInterval(poll, 1500);
    return () => clearInterval(interval);
  }, [poll]);

  // Auto-scroll only within the logs container, not the whole page
  useEffect(() => {
    const el = logsContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [status?.logs]);

  async function startTraining() {
    setStarting(true);
    setError("");
    try {
      await apiFetch("/api/training/start", { method: "POST" });
      // Poll immediately so UI updates right away
      setTimeout(poll, 300);
      setTimeout(poll, 1000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start training. Is the backend running?");
      setStarting(false);
    }
  }

  async function stopTraining() {
    const ok = await confirm({
      title: "Stop the training run?",
      message: "Rounds that already finished are kept. You can start a new run afterwards.",
      confirmLabel: "Stop training",
      danger: true,
    });
    if (!ok) return;
    setStopping(true);
    setError("");
    try {
      await apiFetch("/api/training/stop", { method: "POST" });
      setTimeout(poll, 300);
      setTimeout(poll, 1000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not stop training.");
    } finally {
      setStopping(false);
    }
  }

  // Reset starting flag once polling shows active or has logs
  useEffect(() => {
    if (starting && (status?.active || (status?.logs && status.logs.length > 0))) {
      setStarting(false);
    }
  }, [starting, status?.active, status?.logs]);

  const active = !!status?.active;
  const progress = status && status.total_rounds > 0 ? (status.round / status.total_rounds) * 100 : 0;
  const lastMetric = status?.metrics?.[status.metrics.length - 1];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Federated training"
        description="Run training rounds across the network. Each hospital trains locally; only weight updates are averaged."
        actions={
          <>
            {active && (
              <Button variant="danger-quiet" onClick={stopTraining} loading={stopping}>
                {!stopping && <IconStop size={16} />}
                {stopping ? "Stopping..." : "Stop"}
              </Button>
            )}
            <Button onClick={startTraining} loading={starting} disabled={active}>
              {!starting && !active && <IconPlay size={16} />}
              {starting ? "Starting..." : active ? `Round ${status?.round}/${status?.total_rounds}` : "Start training"}
            </Button>
          </>
        }
      />

      {error && (
        <Notice tone="danger" role="alert">
          {error}
        </Notice>
      )}

      {/* status */}
      <Panel>
        <div className="grid divide-y divide-line sm:grid-cols-[1.4fr_1fr_1fr] sm:divide-x sm:divide-y-0">
          <div className="px-5 py-5 sm:px-6">
            <div className="flex items-center justify-between gap-3">
              <p className="label-mono text-ink-3">Status</p>
              {status === null ? (
                <span className="skeleton h-6 w-20 rounded-full" />
              ) : active || starting ? (
                <Badge tone="accent" dot pulse>
                  {starting && !active ? "Starting" : "Running"}
                </Badge>
              ) : (
                <Badge tone="neutral" dot>
                  Idle
                </Badge>
              )}
            </div>
            <div className="mt-4">
              <div className="flex items-baseline justify-between text-[13px]">
                <span className="text-ink-2">Progress</span>
                <span className="font-mono text-xs text-ink tabular">
                  {status ? `${status.round} / ${status.total_rounds}` : "0 / 0"}
                </span>
              </div>
              <div
                className="mt-2 h-2 overflow-hidden rounded-full bg-sunken"
                role="progressbar"
                aria-label="Training progress"
                aria-valuemin={0}
                aria-valuemax={status?.total_rounds ?? 0}
                aria-valuenow={status?.round ?? 0}
              >
                <div
                  className={`h-full rounded-full bg-accent transition-[width] duration-500 ease-out ${active ? "" : "opacity-60"}`}
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          </div>
          <div className="px-5 py-5 sm:px-6">
            <p className="label-mono text-ink-3">Current loss</p>
            <p className="mt-2 font-mono text-2xl font-medium text-ink tabular">
              {status && (active || status.metrics.length > 0) ? (
                status.loss.toFixed(4)
              ) : (
                <span className="font-sans text-lg font-normal text-ink-3">None yet</span>
              )}
            </p>
          </div>
          <div className="px-5 py-5 sm:px-6">
            <p className="label-mono text-ink-3">Nodes last round</p>
            <p className="mt-2 font-mono text-2xl font-medium text-ink tabular">{lastMetric ? (
                lastMetric.nodes
              ) : (
                <span className="font-sans text-lg font-normal text-ink-3">None yet</span>
              )}</p>
          </div>
        </div>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <Panel>
          <PanelHeader title="Training loss" description="Average loss across participating nodes, per round." />
          <PanelBody>
            {status?.metrics && status.metrics.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={status.metrics} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                    <CartesianGrid stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="round" tick={chart.axisTick} tickLine={false} axisLine={false} />
                    <YAxis tick={chart.axisTick} tickLine={false} axisLine={false} width={52} />
                    <Tooltip
                      {...chart.tooltip}
                      cursor={chart.cursor}
                      labelFormatter={(r) => `Round ${r}`}
                      formatter={(v: number) => [v.toFixed(4), "Avg loss"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="avg_loss"
                      stroke={chart.series}
                      strokeWidth={2}
                      dot={{ r: 3, fill: chart.series, strokeWidth: 0 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState icon={<IconPulse size={18} />} title="No rounds yet">
                Start a training run and the loss curve will build up here round by round.
              </EmptyState>
            )}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Training log" />
          <PanelBody>
            <ol
              ref={logsContainerRef}
              className="h-64 overflow-y-auto rounded border border-line bg-canvas p-3 font-mono text-xs leading-relaxed"
            >
              {status?.logs && status.logs.length > 0 ? (
                status.logs.map((log, i) => (
                  <li key={i} className={logTone(log)}>
                    {log}
                  </li>
                ))
              ) : (
                <li className="text-ink-3">No log output yet.</li>
              )}
            </ol>
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
