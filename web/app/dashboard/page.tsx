"use client";

import { useEffect, useState, useRef, useCallback, FormEvent, ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { apiFetch, ApiError } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
type Tab = "overview" | "data" | "predict" | "training" | "network";

interface PredictionResult {
  predicted_class: string;
  confidence: number;
  is_unknown: boolean;
  message: string;
  class_probabilities: Record<string, number>;
  top_predictions?: { label: string; probability: number }[];
  uncertainty?: number;
}

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

const UPLOAD_BATCH_MAX_FILES = 100;
const UPLOAD_BATCH_MAX_BYTES = 20 * 1024 * 1024;

interface HospitalInfo {
  id: number;
  name: string;
  email?: string;
  location?: string;
}

/* ================================================================== */
/*  DASHBOARD                                                          */
/* ================================================================== */
export default function DashboardPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");
  const [hospital, setHospital] = useState<HospitalInfo | null>(null);

  /* auth guard: session lives in an httpOnly cookie, so we can't just
     check localStorage for a token — ask the backend who (if anyone)
     the current cookie belongs to. */
  useEffect(() => {
    try {
      const stored = localStorage.getItem("hospital");
      if (stored) setHospital(JSON.parse(stored)); // optimistic first paint
    } catch {
      // corrupt/blocked cache — fall through to the authoritative /me check
      localStorage.removeItem("hospital");
    }

    apiFetch<HospitalInfo>("/api/auth/me")
      .then((h) => {
        setHospital(h);
        localStorage.setItem("hospital", JSON.stringify(h));
      })
      .catch((err: unknown) => {
        // Only a 401 means "not signed in". A network blip or a 5xx must
        // not throw away a valid session by bouncing the user to /login.
        if (err instanceof ApiError && err.status === 401) {
          localStorage.removeItem("hospital");
          router.push("/login");
        }
      });
  }, [router]);

  async function logout() {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } catch {
      // even if the network call fails, still clear local state and leave
    }
    localStorage.removeItem("hospital");
    router.push("/");
  }

  if (!hospital) return null;

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "data", label: "Datasets" },
    { key: "predict", label: "Predict" },
    { key: "training", label: "Training" },
    { key: "network", label: "Network" },
  ];

  return (
    <div className="min-h-screen">
      {/* top bar */}
      <header className="border-b border-white/5 bg-[#09090b]/90 backdrop-blur-lg sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="text-lg font-bold">
            <span className="text-white">SecureDerm</span>
            <span className="text-zinc-500 ml-1 text-sm">AI</span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-zinc-400">{hospital.name}</span>
            <button
              onClick={logout}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* tabs */}
      <div className="border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-3 text-sm font-medium transition-colors relative ${
                tab === t.key
                  ? "text-white"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {t.label}
              {tab === t.key && (
                <motion.div
                  layoutId="tab-indicator"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500"
                />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {tab === "overview" && <OverviewTab hospital={hospital} setTab={setTab} />}
        {tab === "data" && <DataTab />}
        {tab === "predict" && <PredictTab />}
        {tab === "training" && <TrainingTab />}
        {tab === "network" && <NetworkTab />}
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  OVERVIEW TAB                                                       */
/* ------------------------------------------------------------------ */
function OverviewTab({ hospital, setTab }: { hospital: HospitalInfo; setTab: (t: Tab) => void }) {
  const [datasets, setDatasets] = useState<{ image_count: number }[]>([]);
  const [models, setModels] = useState<unknown[]>([]);
  const [hospitals, setHospitals] = useState<unknown[]>([]);

  useEffect(() => {
    apiFetch<typeof datasets>("/api/datasets").then(setDatasets).catch(() => {});
    apiFetch<unknown[]>("/api/models").then(setModels).catch(() => {});
    apiFetch<unknown[]>("/api/hospitals").then(setHospitals).catch(() => {});
  }, []);

  const totalImages = datasets.reduce(
    (sum, d) => sum + (d.image_count || 0),
    0,
  );

  const stats = [
    { label: "Hospital", value: hospital.name },
    { label: "Local Images", value: String(totalImages) },
    { label: "Network Models", value: String(models.length) },
    { label: "Network Hospitals", value: String(hospitals.length) },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-8"
    >
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="glass rounded-xl p-5">
            <div className="text-xs text-zinc-500 uppercase tracking-wider">
              {s.label}
            </div>
            <div className="mt-1 text-xl font-bold">{s.value}</div>
          </div>
        ))}
      </div>

      <div className="glass rounded-xl p-6">
        <h3 className="font-semibold mb-4">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => setTab("data")}
            className="px-4 py-2 text-sm rounded-lg bg-indigo-600/20 border border-indigo-500/30 text-indigo-300 hover:bg-indigo-600/30 transition-colors"
          >
            Upload Dataset
          </button>
          <button
            onClick={() => setTab("predict")}
            className="px-4 py-2 text-sm rounded-lg bg-emerald-600/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-600/30 transition-colors"
          >
            Diagnose Wound
          </button>
          <button
            onClick={() => setTab("training")}
            className="px-4 py-2 text-sm rounded-lg bg-purple-600/20 border border-purple-500/30 text-purple-300 hover:bg-purple-600/30 transition-colors"
          >
            Start Training
          </button>
          <Link
            href="/models"
            className="px-4 py-2 text-sm rounded-lg bg-white/5 border border-white/10 text-zinc-300 hover:bg-white/10 transition-colors"
          >
            Browse Models
          </Link>
        </div>
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  DATA TAB                                                           */
/* ------------------------------------------------------------------ */
function DataTab() {
  const [datasets, setDatasets] = useState<
    { id: number; name: string; image_count: number; created_at: string }[]
  >([]);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgIsError, setMsgIsError] = useState(false);

  const loadDatasets = useCallback(() => {
    apiFetch<typeof datasets>("/api/datasets").then(setDatasets).catch(() => {});
  }, []);

  useEffect(() => {
    loadDatasets();
  }, [loadDatasets]);

  async function handleUpload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const input = form.querySelector<HTMLInputElement>('input[type="file"]');
    if (!input?.files?.length) {
      setMsgIsError(true);
      setMsg("Please select image files first.");
      return;
    }

    setUploading(true);
    setMsg("");

    // The backend caps a request at 100 files / 25 MB; send big selections
    // as several requests instead of having the whole upload rejected.
    const batches: File[][] = [];
    let current: File[] = [];
    let currentBytes = 0;
    for (const f of Array.from(input.files)) {
      if (
        current.length > 0 &&
        (current.length >= UPLOAD_BATCH_MAX_FILES ||
          currentBytes + f.size > UPLOAD_BATCH_MAX_BYTES)
      ) {
        batches.push(current);
        current = [];
        currentBytes = 0;
      }
      current.push(f);
      currentBytes += f.size;
    }
    if (current.length > 0) batches.push(current);

    let uploaded = 0;
    let totalImages = 0;
    try {
      for (const batch of batches) {
        const fd = new FormData();
        for (const f of batch) fd.append("files", f);
        const data = await apiFetch<{ uploaded: number; total_images: number }>(
          "/api/datasets/upload",
          { method: "POST", body: fd },
        );
        uploaded += data.uploaded;
        totalImages = data.total_images;
      }
      setMsgIsError(false);
      setMsg(`Uploaded ${uploaded} images (${totalImages} total)`);
      input.value = "";
    } catch (err: unknown) {
      setMsgIsError(true);
      setMsg(
        (uploaded > 0 ? `Uploaded ${uploaded} images before failing: ` : "") +
          (err instanceof Error ? err.message : "Upload failed. Is the backend running?"),
      );
    } finally {
      loadDatasets();
      setUploading(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-8"
    >
      {/* upload */}
      <div className="glass rounded-xl p-6">
        <h3 className="font-semibold mb-4">Upload Wound Images</h3>
        <form onSubmit={handleUpload} className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <input
              type="file"
              multiple
              accept="image/*"
              className="w-full text-sm text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-600/20 file:text-indigo-300 hover:file:bg-indigo-600/30 file:cursor-pointer"
            />
          </div>
          <button
            type="submit"
            disabled={uploading}
            className="px-6 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm font-medium transition-all"
          >
            {uploading ? "Uploading..." : "Upload"}
          </button>
        </form>
        {msg && (
          <p className={`mt-3 text-sm ${
            msgIsError ? "text-rose-400" : "text-emerald-400"
          }`}>{msg}</p>
        )}
      </div>

      {/* list */}
      <div className="glass rounded-xl p-6">
        <h3 className="font-semibold mb-4">Your Datasets</h3>
        {datasets.length === 0 ? (
          <p className="text-sm text-zinc-500">No datasets yet. Upload some images to get started.</p>
        ) : (
          <div className="space-y-3">
            {datasets.map((d) => (
              <div
                key={d.id}
                className="flex items-center justify-between bg-white/5 rounded-lg px-4 py-3"
              >
                <div>
                  <div className="text-sm font-medium">{d.name}</div>
                  <div className="text-xs text-zinc-500">
                    {d.image_count} images
                  </div>
                </div>
                <div className="text-xs text-zinc-600">
                  {d.created_at
                    ? new Date(d.created_at).toLocaleDateString()
                    : ""}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  PREDICT TAB                                                        */
/* ------------------------------------------------------------------ */
function PredictTab() {
  const [preview, setPreview] = useState<string | null>(null);
  const [predicting, setPredicting] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Release the last preview's blob URL when leaving the tab.
  const previewRef = useRef<string | null>(null);
  previewRef.current = preview;
  useEffect(() => {
    return () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    };
  }, []);

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    setResult(null);
    setError("");
    if (preview) URL.revokeObjectURL(preview);
    setPreview(file ? URL.createObjectURL(file) : null);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError("Please select a wound image first.");
      return;
    }

    setPredicting(true);
    setError("");
    setResult(null);

    const fd = new FormData();
    fd.append("file", file);

    try {
      const data = await apiFetch<PredictionResult>("/api/predict", {
        method: "POST",
        body: fd,
      });
      setResult(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Prediction failed. Is a trained model available?",
      );
    } finally {
      setPredicting(false);
    }
  }

  const sortedProbabilities = result
    ? Object.entries(result.class_probabilities).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-8"
    >
      <div className="glass rounded-xl p-6">
        <h3 className="font-semibold mb-4">Diagnose a Wound Image</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[200px]">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="w-full text-sm text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-emerald-600/20 file:text-emerald-300 hover:file:bg-emerald-600/30 file:cursor-pointer"
              />
            </div>
            <button
              type="submit"
              disabled={predicting}
              className="px-6 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-sm font-medium transition-all"
            >
              {predicting ? "Analyzing..." : "Analyze"}
            </button>
          </div>

          {preview && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={preview}
              alt="Selected wound"
              className="max-h-64 rounded-lg border border-white/10 object-contain"
            />
          )}

          {error && (
            <p className="text-sm text-rose-400">{error}</p>
          )}
        </form>
      </div>

      {result && (
        <div className="glass rounded-xl p-6 space-y-5">
          <div
            className={`rounded-lg px-4 py-3 border ${
              result.is_unknown
                ? "bg-amber-400/10 border-amber-400/30 text-amber-300"
                : "bg-emerald-400/10 border-emerald-400/30 text-emerald-300"
            }`}
          >
            <div className="text-sm font-medium">
              {result.is_unknown ? "Unrecognized pattern" : result.predicted_class}
            </div>
            <div className="text-xs mt-1 opacity-80">{result.message}</div>
          </div>

          {result.top_predictions && result.top_predictions.length > 0 && (
            <div>
              <h4 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">
                Most Likely Diagnoses
              </h4>
              <ol className="space-y-1 text-sm text-zinc-300">
                {result.top_predictions.map((p, i) => (
                  <li key={p.label} className="flex justify-between">
                    <span>
                      {i + 1}. {p.label}
                    </span>
                    <span className="text-zinc-500">
                      {(p.probability * 100).toFixed(1)}%
                    </span>
                  </li>
                ))}
              </ol>
              {typeof result.uncertainty === "number" && (
                <p className="mt-2 text-xs text-zinc-600">
                  Model uncertainty: {(result.uncertainty * 100).toFixed(0)}%
                </p>
              )}
            </div>
          )}

          <div>
            <h4 className="text-xs text-zinc-500 uppercase tracking-wider mb-3">
              Class Probabilities
            </h4>
            <div className="space-y-2">
              {sortedProbabilities.map(([className, prob]) => (
                <div key={className}>
                  <div className="flex justify-between text-xs text-zinc-400 mb-1">
                    <span>{className}</span>
                    <span>{(prob * 100).toFixed(1)}%</span>
                  </div>
                  <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full"
                      style={{ width: `${prob * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  TRAINING TAB                                                       */
/* ------------------------------------------------------------------ */
function TrainingTab() {
  const [status, setStatus] = useState<TrainingStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const logsContainerRef = useRef<HTMLDivElement>(null);

  const poll = useCallback(() => {
    apiFetch<TrainingStatus>("/api/training/status")
      .then(setStatus)
      .catch(() => {});
  }, []);

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

  // Reset starting flag once polling shows active or has logs
  useEffect(() => {
    if (starting && (status?.active || (status?.logs && status.logs.length > 0))) {
      setStarting(false);
    }
  }, [starting, status?.active, status?.logs]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-8"
    >
      {/* control */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Federated Training</h3>
          <button
            onClick={startTraining}
            disabled={starting || !!status?.active}
            className="px-6 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm font-medium transition-all"
          >
            {starting
              ? "Starting..."
              : status?.active
                ? `Round ${status.round}/${status.total_rounds}...`
                : "Start Training"}
          </button>
        </div>

        {error && (
          <div className="text-sm text-rose-400 bg-rose-400/10 border border-rose-400/20 rounded-lg px-4 py-2 mb-4">
            {error}
          </div>
        )}

        {status && (status.active || starting) && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-zinc-400">
              <span>Progress</span>
              <span>
                {status.round}/{status.total_rounds}
              </span>
            </div>
            <div className="h-2 bg-white/5 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full"
                animate={{
                  width: `${(status.round / status.total_rounds) * 100}%`,
                }}
                transition={{ duration: 0.5 }}
              />
            </div>
            <div className="text-xs text-zinc-500">
              Current loss: {status.loss.toFixed(4)}
            </div>
          </div>
        )}
      </div>

      {/* chart */}
      {status?.metrics && status.metrics.length > 0 && (
        <div className="glass rounded-xl p-6">
          <h3 className="font-semibold mb-4">Training Loss</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={status.metrics}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey="round"
                  stroke="#52525b"
                  tick={{ fontSize: 12 }}
                  label={{
                    value: "Round",
                    position: "insideBottom",
                    offset: -4,
                    fill: "#71717a",
                    fontSize: 12,
                  }}
                />
                <YAxis
                  stroke="#52525b"
                  tick={{ fontSize: 12 }}
                  label={{
                    value: "Loss",
                    angle: -90,
                    position: "insideLeft",
                    fill: "#71717a",
                    fontSize: 12,
                  }}
                />
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
                  dataKey="avg_loss"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={{ fill: "#6366f1", r: 4 }}
                  activeDot={{ r: 6, fill: "#818cf8" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* logs */}
      {status?.logs && status.logs.length > 0 && (
        <div className="glass rounded-xl p-6">
          <h3 className="font-semibold mb-4">Training Logs</h3>
          <div ref={logsContainerRef} className="bg-black/40 rounded-lg p-4 max-h-64 overflow-y-auto font-mono text-xs leading-relaxed">
            {status.logs.map((log, i) => (
              <div
                key={i}
                className={
                  log.includes("Complete") || log.includes("complete")
                    ? "text-emerald-400"
                    : log.includes("uploading") || log.includes("merging")
                      ? "text-indigo-400"
                      : "text-zinc-400"
                }
              >
                {log}
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  NETWORK TAB                                                        */
/* ------------------------------------------------------------------ */
function NetworkTab() {
  const [hospitals, setHospitals] = useState<HospitalInfo[]>([]);
  const [rounds, setRounds] = useState<
    {
      round_number: number;
      participating_hospitals: string;
      avg_loss: number;
      created_at: string;
    }[]
  >([]);

  useEffect(() => {
    apiFetch<HospitalInfo[]>("/api/hospitals").then(setHospitals).catch(() => {});
    apiFetch<typeof rounds>("/api/federated/rounds").then(setRounds).catch(() => {});
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-8"
    >
      {/* hospitals */}
      <div className="glass rounded-xl p-6">
        <h3 className="font-semibold mb-4">Network Hospitals</h3>
        {hospitals.length === 0 ? (
          <p className="text-sm text-zinc-500">No hospitals registered yet.</p>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {hospitals.map((h) => (
              <div
                key={h.id}
                className="bg-white/5 rounded-lg px-4 py-3 flex items-center gap-3"
              >
                <div className="w-8 h-8 rounded-full bg-indigo-600/20 flex items-center justify-center text-xs font-bold text-indigo-300">
                  {h.name.charAt(0)}
                </div>
                <div>
                  <div className="text-sm font-medium">{h.name}</div>
                  <div className="text-xs text-zinc-500">
                    {h.location || "—"}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* rounds */}
      <div className="glass rounded-xl p-6">
        <h3 className="font-semibold mb-4">Federated Rounds</h3>
        {rounds.length === 0 ? (
          <p className="text-sm text-zinc-500">
            No rounds yet. Start training to see results.
          </p>
        ) : (
          <div className="space-y-2">
            {rounds.map((r) => (
              <div
                key={r.round_number + (r.created_at || "")}
                className="flex items-center justify-between bg-white/5 rounded-lg px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-purple-600/20 flex items-center justify-center text-xs font-bold text-purple-300">
                    R{r.round_number}
                  </div>
                  <div className="text-sm text-zinc-400">
                    {r.participating_hospitals}
                  </div>
                </div>
                <div className="text-sm font-mono text-zinc-300">
                  {r.avg_loss.toFixed(4)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
