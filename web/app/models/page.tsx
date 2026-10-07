"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { apiFetch } from "@/lib/api";

interface Model {
  id: number;
  model_name: string;
  version: number;
  accuracy: number;
  description: string;
  hospital_count: number;
  created_at: string | null;
}

export default function ModelsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    apiFetch<Model[]>("/api/models")
      .then(setModels)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Navbar />
      <main className="min-h-screen pt-24 pb-20 px-6">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center mb-12"
          >
            <span className="text-sm font-medium text-indigo-400 uppercase tracking-widest">
              Model Marketplace
            </span>
            <h1 className="mt-3 text-3xl sm:text-4xl font-bold">
              Federated Models
            </h1>
            <p className="mt-2 text-zinc-400 max-w-lg mx-auto">
              Browse privacy-preserving models trained across the SecureDerm
              hospital network. Each model was built without sharing patient
              data.
            </p>
          </motion.div>

          {loading ? (
            <p className="text-center text-zinc-500">Loading models...</p>
          ) : error ? (
            <p className="text-center text-rose-400">
              Could not load models. Is the backend running?
            </p>
          ) : models.length === 0 ? (
            <p className="text-center text-zinc-500">
              No models available yet.
            </p>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {models.map((m, i) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.08 }}
                  whileHover={{ y: -4 }}
                  className="glass rounded-2xl p-6 flex flex-col justify-between hover:glow-border transition-all"
                >
                  <div>
                    <div className="flex items-start justify-between">
                      <h3 className="font-semibold text-sm leading-tight">
                        {m.model_name}
                      </h3>
                      <span className="text-xs text-zinc-600 shrink-0 ml-2">
                        v{m.version}
                      </span>
                    </div>
                    <p
                      className={`mt-3 text-xs text-zinc-400 leading-relaxed ${
                        expandedId === m.id ? "" : "line-clamp-3"
                      }`}
                    >
                      {m.description}
                    </p>
                  </div>

                  <div className="mt-6 flex items-center justify-between border-t border-white/5 pt-4">
                    <div className="flex items-center gap-4">
                      <div>
                        <div className="text-xs text-zinc-500">Accuracy</div>
                        <div className="text-sm font-bold text-emerald-400">
                          {(m.accuracy * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500">Hospitals</div>
                        <div className="text-sm font-bold text-indigo-400">
                          {m.hospital_count}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => setExpandedId(expandedId === m.id ? null : m.id)}
                      aria-expanded={expandedId === m.id}
                      className="px-3 py-1.5 text-xs rounded-lg bg-indigo-600/20 border border-indigo-500/30 text-indigo-300 hover:bg-indigo-600/30 transition-colors"
                    >
                      {expandedId === m.id ? "Less" : "Details"}
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
