"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import PageIntro from "@/components/marketing/PageIntro";
import FederationGraph, { FED_NODES, type FedPhase } from "@/components/FederationGraph";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { IconPlay, IconPulse } from "@/components/ui/icons";
import { chart } from "@/lib/chart";

interface RoundData {
  round: number;
  loss: number;
}

type LogKind = "train" | "send" | "merge" | "model" | "done";
interface LogLine {
  kind: LogKind;
  text: string;
}

const TOTAL_ROUNDS = 5;
const BASE_LOSS = 2.45;

const PHASES: { key: Exclude<FedPhase, "idle">; label: string; detail: string }[] = [
  { key: "training", label: "Train", detail: "Hospitals train locally with differential privacy" },
  { key: "uploading", label: "Send", detail: "Encrypted weight updates go to the aggregator" },
  { key: "aggregating", label: "Average", detail: "The aggregator runs Federated Averaging" },
  { key: "distributing", label: "Return", detail: "The improved global model goes back to every site" },
];

const LOG_COLOR: Record<LogKind, string> = {
  train: "text-ink-2",
  send: "text-accent-ink",
  merge: "text-ink",
  model: "text-accent-ink",
  done: "text-ok-ink font-medium",
};

export default function DemoPage() {
  const [running, setRunning] = useState(false);
  const [round, setRound] = useState(0);
  const [phase, setPhase] = useState<FedPhase>("idle");
  const [metrics, setMetrics] = useState<RoundData[]>([]);
  const [log, setLog] = useState<LogLine[]>([]);
  const logRef = useRef<HTMLOListElement>(null);

  const addLog = useCallback((kind: LogKind, text: string) => {
    setLog((prev) => [...prev.slice(-30), { kind, text }]);
  }, []);

  // Keep the newest log line in view without scrolling the page.
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [log]);

  // The loop below sleeps ~30 s in total; without this flag it keeps calling
  // setState (and never stops) after the user navigates away.
  const cancelled = useRef(false);
  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
    };
  }, []);

  const runSimulation = useCallback(async () => {
    setRunning(true);
    setMetrics([]);
    setLog([]);
    setRound(0);

    for (let r = 1; r <= TOTAL_ROUNDS; r++) {
      if (cancelled.current) return;
      setRound(r);

      setPhase("training");
      addLog("train", `[round ${r}] ${FED_NODES.length} hospitals training locally`);
      await sleep(2000);

      setPhase("uploading");
      addLog("send", `[round ${r}] encrypted updates uploaded`);
      await sleep(1500);

      setPhase("aggregating");
      addLog("merge", `[round ${r}] aggregator running FedAvg`);
      await sleep(1500);

      setPhase("distributing");
      const loss = BASE_LOSS * Math.pow(0.82, r) + (Math.random() - 0.5) * 0.06;
      setMetrics((prev) => [...prev, { round: r, loss: +loss.toFixed(4) }]);
      addLog("model", `[round ${r}] global model updated, loss ${loss.toFixed(4)}`);
      await sleep(1500);
    }

    if (cancelled.current) return;
    setPhase("idle");
    addLog("done", "Simulation complete. The global model is ready.");
    setRunning(false);
  }, [addLog]);

  const phaseIndex = PHASES.findIndex((p) => p.key === phase);
  const done = !running && metrics.length === TOTAL_ROUNDS;
  const statusText = running
    ? PHASES[phaseIndex]?.detail ?? "Starting"
    : done
      ? "Simulation complete"
      : "Ready to simulate";

  return (
    <>
      <Navbar />
      <main id="main">
        <PageIntro
          eyebrow="Interactive simulation"
          title="Federated learning, one round at a time"
          actions={
            <Button size="lg" onClick={runSimulation} loading={running} className="w-full md:w-auto">
              {!running && <IconPlay size={16} />}
              {running ? `Round ${round} of ${TOTAL_ROUNDS}` : done ? "Run again" : "Run simulation"}
            </Button>
          }
        >
          Watch four hospitals improve a shared model without exchanging patient data. This page is a
          visual simulation; the numbers are generated in your browser.
        </PageIntro>

        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 sm:px-6 lg:grid-cols-[1.5fr_1fr]">
          <Panel className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5 sm:px-6">
              <h2 className="text-[15px] font-semibold text-ink">Network</h2>
              <Badge tone={running ? "accent" : done ? "success" : "neutral"} dot pulse={running}>
                {running ? `Round ${round} / ${TOTAL_ROUNDS}` : done ? "Complete" : "Idle"}
              </Badge>
            </div>
            <div className="grid-paper">
              <FederationGraph phase={phase} round={round || undefined} className="aspect-square w-full sm:aspect-[16/10]" />
            </div>

            {/* phase stepper */}
            <div className="border-t border-line px-5 py-4 sm:px-6">
              <ol className="grid grid-cols-4 gap-2" aria-label="Round phases">
                {PHASES.map((p, i) => {
                  const state = !running ? "todo" : i < phaseIndex ? "past" : i === phaseIndex ? "now" : "todo";
                  return (
                    <li key={p.key} aria-current={state === "now" ? "step" : undefined}>
                      <span
                        className={`block h-1 rounded-full transition-colors duration-300 ${
                          state === "now" ? "bg-accent" : state === "past" ? "bg-accent/40" : "bg-line"
                        }`}
                      />
                      <span
                        className={`mt-2 block text-xs font-medium transition-colors ${
                          state === "now" ? "text-ink" : "text-ink-3"
                        }`}
                      >
                        {p.label}
                      </span>
                    </li>
                  );
                })}
              </ol>
              <p className="mt-3 text-[13px] text-ink-2" role="status" aria-live="polite">
                {statusText}
              </p>
            </div>
          </Panel>

          <div className="grid gap-6">
            <Panel>
              <PanelHeader title="Training loss" description="Global model loss after each round." />
              <PanelBody>
                {metrics.length === 0 ? (
                  <div className="flex h-44 flex-col items-center justify-center rounded border border-dashed border-line-strong text-center">
                    <IconPulse size={18} className="text-ink-3" />
                    <p className="mt-2 text-[13px] text-ink-3">The curve appears after round 1.</p>
                  </div>
                ) : (
                  <div className="h-44">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={metrics} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                        <CartesianGrid stroke={chart.grid} vertical={false} />
                        <XAxis
                          dataKey="round"
                          tick={chart.axisTick}
                          tickLine={false}
                          axisLine={false}
                          domain={[1, TOTAL_ROUNDS]}
                          type="number"
                          ticks={[1, 2, 3, 4, 5]}
                        />
                        <YAxis tick={chart.axisTick} tickLine={false} axisLine={false} width={44} />
                        <Tooltip
                          {...chart.tooltip}
                          cursor={chart.cursor}
                          labelFormatter={(r) => `Round ${r}`}
                          formatter={(v: number) => [v.toFixed(4), "Loss"]}
                        />
                        <Line
                          type="monotone"
                          dataKey="loss"
                          stroke={chart.series}
                          strokeWidth={2}
                          dot={{ r: 3, fill: chart.series, strokeWidth: 0 }}
                          activeDot={{ r: 5 }}
                          isAnimationActive={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader title="Event log" />
              <PanelBody>
                <ol
                  ref={logRef}
                  className="h-44 overflow-y-auto rounded border border-line bg-canvas p-3 font-mono text-xs leading-relaxed"
                  aria-live="off"
                >
                  {log.length === 0 ? (
                    <li className="text-ink-3">Waiting for the simulation to start.</li>
                  ) : (
                    log.map((l, i) => (
                      <li key={i} className={LOG_COLOR[l.kind]}>
                        {l.text}
                      </li>
                    ))
                  )}
                </ol>
              </PanelBody>
            </Panel>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
