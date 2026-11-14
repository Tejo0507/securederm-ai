"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useOverflows } from "@/lib/useOverflows";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import PageIntro from "@/components/marketing/PageIntro";
import { apiFetch } from "@/lib/api";
import Badge from "@/components/ui/Badge";
import DepthMeter from "@/components/ui/DepthMeter";
import Button, { buttonClass } from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { IconAlert, IconChip, IconHospital } from "@/components/ui/icons";

interface Model {
  id: number;
  model_name: string;
  version: number;
  accuracy: number;
  description: string;
  hospital_count: number;
  created_at: string | null;
}

/** A two-line description with a "Read more" toggle only when lines are actually hidden. */
function ModelDescription({
  id,
  text,
  expanded,
  onToggle,
}: {
  id: string;
  text: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  const ref = useRef<HTMLParagraphElement>(null);
  const clamped = useOverflows(ref, !expanded);
  return (
    <>
      <p
        ref={ref}
        id={id}
        className={`mt-2 max-w-2xl text-sm leading-relaxed text-ink-2 ${expanded ? "" : "line-clamp-2"}`}
      >
        {text}
      </p>
      {(clamped || expanded) && (
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-controls={id}
          className="mt-2 text-[13px] font-medium text-accent-ink underline-offset-4 hover:underline"
        >
          {expanded ? "Show less" : "Read more"}
        </button>
      )}
    </>
  );
}

export default function ModelsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(false);
    apiFetch<Model[]>("/api/models")
      .then(setModels)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  return (
    <>
      <Navbar />
      <main id="main" className="min-h-[70vh]">
        <PageIntro eyebrow="Model registry" title="Federated models">
          Privacy-preserving models trained across the SecureDerm hospital network. Each was built
          without any hospital sharing patient images.
        </PageIntro>

        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
          {loading ? (
            <ul className="space-y-3" aria-busy="true" aria-label="Loading models">
              {[0, 1, 2].map((i) => (
                <li key={i} className="rounded-lg border border-line bg-surface p-6">
                  <div className="skeleton h-4 w-48" />
                  <div className="skeleton mt-4 h-3 w-full max-w-xl" />
                  <div className="skeleton mt-2 h-3 w-2/3 max-w-md" />
                </li>
              ))}
            </ul>
          ) : error ? (
            <EmptyState
              icon={<IconAlert size={18} />}
              title="Could not load models"
              action={
                <Button variant="secondary" onClick={load}>
                  Try again
                </Button>
              }
            >
              The model registry did not respond. Check that the backend is running.
            </EmptyState>
          ) : models.length === 0 ? (
            <EmptyState
              icon={<IconChip size={18} />}
              title="No models published yet"
              action={
                <Link href="/signup" className={buttonClass("primary")}>
                  Register a hospital
                </Link>
              }
            >
              Models appear here after the network completes its first federated training run.
            </EmptyState>
          ) : (
            <>
              <div className="mb-4 flex items-baseline justify-between">
                <p className="text-sm text-ink-2">
                  <span className="font-medium text-ink tabular">{models.length}</span>{" "}
                  {models.length === 1 ? "model" : "models"}
                </p>
              </div>
              <ul className="overflow-hidden rounded-xl border border-line bg-surface shadow-slab">
                {models.map((m) => {
                  const expanded = expandedId === m.id;
                  const pct = Math.max(0, Math.min(100, m.accuracy * 100));
                  return (
                    <li
                      key={m.id}
                      className="grid gap-5 border-b border-line p-5 transition-colors last:border-b-0 hover:bg-canvas/60 sm:p-6 md:grid-cols-[1fr_auto] md:gap-10"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="text-[15px] font-semibold text-ink">{m.model_name}</h2>
                          <Badge tone="neutral" className="font-mono">
                            v{m.version}
                          </Badge>
                        </div>
                        <ModelDescription
                          id={`model-desc-${m.id}`}
                          text={m.description}
                          expanded={expanded}
                          onToggle={() => setExpandedId(expanded ? null : m.id)}
                        />
                      </div>

                      <dl className="grid grid-cols-3 gap-6 md:w-[360px]">
                        <div className="col-span-1">
                          <dt className="label-mono text-ink-3">Accuracy</dt>
                          <dd className="mt-1.5 text-lg font-semibold text-ink tabular">{pct.toFixed(1)}%</dd>
                          <dd className="mt-2">
                            <DepthMeter value={pct / 100} label={`${m.model_name} accuracy`} segments={16} />
                          </dd>
                        </div>
                        <div>
                          <dt className="label-mono text-ink-3">Hospitals</dt>
                          <dd className="mt-1.5 flex items-center gap-1.5 text-lg font-semibold text-ink tabular">
                            <IconHospital size={16} className="text-ink-3" />
                            {m.hospital_count}
                          </dd>
                        </div>
                        <div>
                          <dt className="label-mono text-ink-3">Published</dt>
                          <dd className="mt-1.5 text-sm text-ink tabular">
                            {m.created_at ? new Date(m.created_at).toLocaleDateString() : "Not recorded"}
                          </dd>
                        </div>
                      </dl>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
