"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

/* ------------------------------------------------------------------ */
/*  Types + constants                                                  */
/* ------------------------------------------------------------------ */
interface RoundData {
  round: number;
  loss: number;
}

const HOSPITAL_NODES = [
  { id: "A", label: "Hospital A", x: 10, y: 30 },
  { id: "B", label: "Hospital B", x: 10, y: 70 },
  { id: "C", label: "Hospital C", x: 90, y: 30 },
  { id: "D", label: "Hospital D", x: 90, y: 70 },
];

const TOTAL_ROUNDS = 5;
const BASE_LOSS = 2.45;

/* ================================================================== */
/*  DEMO PAGE                                                          */
/* ================================================================== */
export default function DemoPage() {
  const [running, setRunning] = useState(false);
  const [round, setRound] = useState(0);
  const [phase, setPhase] = useState<
    "idle" | "training" | "uploading" | "aggregating" | "distributing"
  >("idle");
  const [metrics, setMetrics] = useState<RoundData[]>([]);
  const [log, setLog] = useState<string[]>([]);
  const [activeNodes, setActiveNodes] = useState<string[]>([]);

  const addLog = useCallback((msg: string) => {
    setLog((prev) => [...prev.slice(-30), msg]);
  }, []);

  /* ---------- simulation loop ---------- */
  const runSimulation = useCallback(async () => {
    setRunning(true);
    setMetrics([]);
    setLog([]);
    setRound(0);

    for (let r = 1; r <= TOTAL_ROUNDS; r++) {
      setRound(r);

      /* phase 1: local training */
      setPhase("training");
      setActiveNodes(HOSPITAL_NODES.map((n) => n.id));
      addLog(`[Round ${r}] All hospitals training locally...`);
      await sleep(2000);

      /* phase 2: upload gradients */
      setPhase("uploading");
      addLog(`[Round ${r}] Encrypted gradients being uploaded`);
      await sleep(1500);

      /* phase 3: aggregation */
      setPhase("aggregating");
      setActiveNodes([]);
      addLog(`[Round ${r}] Aggregator running FedAvg`);
      await sleep(1500);

      /* phase 4: distribute */
      setPhase("distributing");
      const loss =
        BASE_LOSS * Math.pow(0.82, r) + (Math.random() - 0.5) * 0.06;
      setMetrics((prev) => [...prev, { round: r, loss: +loss.toFixed(4) }]);
      addLog(`[Round ${r}] Global model updated — loss: ${loss.toFixed(4)}`);
      await sleep(1500);
    }

    setPhase("idle");
    setActiveNodes([]);
    addLog("✓ Simulation complete! Global model is ready.");
    setRunning(false);
  }, [addLog]);

  return (
    <>
      <Navbar />
      <main className="min-h-screen pt-24 pb-20 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center mb-12"
          >
            <span className="text-sm font-medium text-indigo-400 uppercase tracking-widest">
              Interactive Demo
            </span>
            <h1 className="mt-3 text-3xl sm:text-4xl font-bold">
              Federated Learning in Action
            </h1>
            <p className="mt-2 text-zinc-400 max-w-lg mx-auto">
              Watch how hospitals collaboratively train an AI model without
              sharing patient data. This is a simulated visualization.
            </p>
          </motion.div>

          {/* start button */}
          <div className="text-center mb-10">
            <button
              onClick={runSimulation}
              disabled={running}
              className="px-8 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm font-medium shadow-lg shadow-indigo-500/25 transition-all"
            >
              {running
                ? `Round ${round} / ${TOTAL_ROUNDS}...`
                : "Run Simulation"}
            </button>
          </div>

          {/* network visualization */}
          <div className="glass rounded-2xl p-8 mb-8">
            <h3 className="font-semibold mb-6 text-center text-sm text-zinc-400">
              Network Visualization
            </h3>
            <div className="relative w-full" style={{ paddingBottom: "50%" }}>
              <div className="absolute inset-0">
                {/* connection lines */}
                <svg className="absolute inset-0 w-full h-full">
                  {HOSPITAL_NODES.map((n) => (
                    <motion.line
                      key={n.id}
                      x1={`${n.x}%`}
                      y1={`${n.y}%`}
                      x2="50%"
                      y2="50%"
                      stroke={
                        phase === "uploading" && activeNodes.includes(n.id)
                          ? "#6366f1"
                          : phase === "distributing"
                            ? "#8b5cf6"
                            : "#27272a"
                      }
                      strokeWidth={2}
                      strokeDasharray={
                        phase === "uploading" || phase === "distributing"
                          ? "6 4"
                          : "none"
                      }
                      animate={{
                        opacity:
                          phase === "uploading" || phase === "distributing"
                            ? [0.3, 1, 0.3]
                            : 0.3,
                      }}
                      transition={{ repeat: Infinity, duration: 1 }}
                    />
                  ))}
                </svg>

                {/* aggregator (center) */}
                <motion.div
                  className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-24 rounded-2xl flex flex-col items-center justify-center text-center"
                  animate={{
                    backgroundColor:
                      phase === "aggregating"
                        ? "rgba(99, 102, 241, 0.3)"
                        : "rgba(99, 102, 241, 0.1)",
                    scale: phase === "aggregating" ? 1.1 : 1,
                    boxShadow:
                      phase === "aggregating"
                        ? "0 0 40px rgba(99,102,241,0.4)"
                        : "0 0 0px rgba(99,102,241,0)",
                  }}
                  style={{ border: "1px solid rgba(99,102,241,0.3)" }}
                >
                  <span className="text-xl">🔗</span>
                  <span className="text-[10px] text-zinc-400 mt-1">
                    Aggregator
                  </span>
                </motion.div>

                {/* hospital nodes */}
                {HOSPITAL_NODES.map((n) => (
                  <motion.div
                    key={n.id}
                    className="absolute w-20 h-20 -translate-x-1/2 -translate-y-1/2 rounded-xl flex flex-col items-center justify-center text-center border"
                    style={{ left: `${n.x}%`, top: `${n.y}%` }}
                    animate={{
                      backgroundColor:
                        phase === "training" && activeNodes.includes(n.id)
                          ? "rgba(16, 185, 129, 0.15)"
                          : "rgba(255,255,255,0.03)",
                      borderColor:
                        phase === "training" && activeNodes.includes(n.id)
                          ? "rgba(16, 185, 129, 0.4)"
                          : "rgba(255,255,255,0.08)",
                      scale:
                        phase === "training" && activeNodes.includes(n.id)
                          ? 1.08
                          : 1,
                    }}
                  >
                    <span className="text-lg">🏥</span>
                    <span className="text-[10px] text-zinc-400 mt-0.5">
                      {n.label}
                    </span>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* phase indicator */}
            <AnimatePresence mode="wait">
              <motion.div
                key={phase}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                className="text-center mt-4 text-sm"
              >
                {phase === "idle" && (
                  <span className="text-zinc-500">
                    {metrics.length > 0
                      ? "Simulation complete"
                      : "Ready to simulate"}
                  </span>
                )}
                {phase === "training" && (
                  <span className="text-emerald-400">
                    Hospitals training locally with differential privacy...
                  </span>
                )}
                {phase === "uploading" && (
                  <span className="text-indigo-400">
                    Uploading encrypted gradient updates...
                  </span>
                )}
                {phase === "aggregating" && (
                  <span className="text-purple-400">
                    Aggregator running Federated Averaging...
                  </span>
                )}
                {phase === "distributing" && (
                  <span className="text-indigo-400">
                    Distributing improved global model...
                  </span>
                )}
              </motion.div>
            </AnimatePresence>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* chart */}
            <div className="glass rounded-2xl p-6">
              <h3 className="font-semibold mb-4 text-sm">Training Loss</h3>
              {metrics.length === 0 ? (
                <div className="h-48 flex items-center justify-center text-sm text-zinc-600">
                  Run the simulation to see the loss curve
                </div>
              ) : (
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={metrics}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                      <XAxis dataKey="round" stroke="#52525b" tick={{ fontSize: 11 }} />
                      <YAxis stroke="#52525b" tick={{ fontSize: 11 }} />
                      <Tooltip
                        contentStyle={{
                          background: "#18181b",
                          border: "1px solid #27272a",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="loss"
                        stroke="#6366f1"
                        strokeWidth={2}
                        dot={{ fill: "#6366f1", r: 4 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* logs */}
            <div className="glass rounded-2xl p-6">
              <h3 className="font-semibold mb-4 text-sm">Event Log</h3>
              <div className="bg-black/40 rounded-lg p-4 h-48 overflow-y-auto font-mono text-xs leading-relaxed">
                {log.length === 0 ? (
                  <span className="text-zinc-600">Waiting for simulation...</span>
                ) : (
                  log.map((l, i) => (
                    <div
                      key={i}
                      className={
                        l.startsWith("✓")
                          ? "text-emerald-400"
                          : l.includes("Aggregator")
                            ? "text-purple-400"
                            : l.includes("gradients") || l.includes("updated")
                              ? "text-indigo-400"
                              : "text-zinc-400"
                      }
                    >
                      {l}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}

/* ------------------------------------------------------------------ */
function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
