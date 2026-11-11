"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { HospitalInfo } from "@/lib/types";
import SectionHeader from "@/components/dashboard/SectionHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import EmptyState from "@/components/ui/EmptyState";
import { IconHospital, IconMerge } from "@/components/ui/icons";

interface Round {
  round_number: number;
  participating_hospitals: string;
  avg_loss: number;
  created_at: string;
}

export default function NetworkTab() {
  const [hospitals, setHospitals] = useState<HospitalInfo[] | null>(null);
  const [rounds, setRounds] = useState<Round[] | null>(null);

  useEffect(() => {
    apiFetch<HospitalInfo[]>("/api/hospitals").then(setHospitals).catch(() => setHospitals([]));
    apiFetch<Round[]>("/api/federated/rounds").then(setRounds).catch(() => setRounds([]));
  }, []);

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Network"
        description="Hospitals registered in the federation and the training rounds they have completed together."
      />

      <Panel>
        <PanelHeader
          title="Hospitals"
          description={hospitals && hospitals.length > 0 ? `${hospitals.length} registered nodes` : undefined}
        />
        <PanelBody>
          {hospitals === null ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label="Loading hospitals">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton h-[60px]" />
              ))}
            </div>
          ) : hospitals.length === 0 ? (
            <EmptyState icon={<IconHospital size={18} />} title="No hospitals registered yet">
              Hospitals appear here once they create an account and verify their email.
            </EmptyState>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {hospitals.map((h) => (
                <li
                  key={h.id}
                  className="flex items-center gap-3 rounded-lg border border-line bg-canvas/50 px-4 py-3 transition-colors hover:border-line-strong"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line-strong bg-surface font-mono text-xs font-medium text-ink">
                    {h.name.charAt(0).toUpperCase()}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">{h.name}</p>
                    <p className="truncate text-xs text-ink-3">{h.location || "Location not set"}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>

      <Panel className="overflow-hidden">
        <PanelHeader title="Federated rounds" description="Each row is one aggregation of hospital updates." />
        <PanelBody className="pt-4">
          {rounds === null ? (
            <div className="space-y-2" aria-busy="true" aria-label="Loading rounds">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton h-11 w-full" />
              ))}
            </div>
          ) : rounds.length === 0 ? (
            <EmptyState icon={<IconMerge size={18} />} title="No rounds yet">
              Start training to run the first federated round.
            </EmptyState>
          ) : (
            <div className="relative -mx-5 overflow-x-auto sm:-mx-6">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-y border-line bg-canvas text-left">
                    <th scope="col" className="label-mono px-5 py-2.5 font-medium text-ink-3 sm:px-6">
                      Round
                    </th>
                    <th scope="col" className="label-mono px-4 py-2.5 font-medium text-ink-3">
                      Participants
                    </th>
                    <th scope="col" className="label-mono px-4 py-2.5 text-right font-medium text-ink-3">
                      Avg loss
                    </th>
                    <th scope="col" className="label-mono px-5 py-2.5 text-right font-medium text-ink-3 sm:px-6">
                      Completed
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rounds.map((r) => (
                    <tr key={r.round_number + (r.created_at || "")} className="border-b border-line last:border-b-0 hover:bg-canvas/60">
                      <td className="px-5 py-3 sm:px-6">
                        <span className="inline-flex h-6 min-w-[2.25rem] items-center justify-center rounded border border-line-strong bg-surface px-1.5 font-mono text-xs font-medium text-ink">
                          R{r.round_number}
                        </span>
                      </td>
                      <td className="max-w-[320px] px-4 py-3 text-ink-2">
                        <span className="line-clamp-2">{r.participating_hospitals}</span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-[13px] text-ink tabular">{r.avg_loss.toFixed(4)}</td>
                      <td className="px-5 py-3 text-right font-mono text-xs text-ink-3 tabular sm:px-6">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : "Not recorded"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
