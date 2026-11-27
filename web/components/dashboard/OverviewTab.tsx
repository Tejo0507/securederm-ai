"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { DatasetSummary, HospitalInfo, NetworkStats } from "@/lib/types";
import { formatBytes } from "@/components/ui/FileDrop";
import type { Tab } from "@/components/dashboard/tabs";
import SectionHeader from "@/components/dashboard/SectionHeader";
import { Panel, PanelBody, PanelHeader, StatStrip } from "@/components/ui/Panel";
import EmptyState from "@/components/ui/EmptyState";
import {
  IconArrowRight,
  IconArrowUpRight,
  IconChip,
  IconHistory,
  IconPulse,
  IconScan,
  IconUpload,
} from "@/components/ui/icons";

interface ActivityEntry {
  ts: string;
  action: string;
  images?: number;
  rounds?: number;
  round?: number;
  rows?: number;
  ip?: string;
}

/** The short qualifier after an event's name ("6 images", "at round 3"), if it has one. */
export function activityDetail(e: ActivityEntry): string | null {
  const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
  if (e.action === "training_stopped" && typeof e.round === "number") return `at round ${e.round}`;
  if (typeof e.rounds === "number") return plural(e.rounds, "round");
  if (typeof e.images === "number") return plural(e.images, "image");
  if (typeof e.rows === "number") return plural(e.rows, "row");
  return null;
}

function ActionRow({
  icon,
  title,
  body,
  onClick,
  href,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  onClick?: () => void;
  href?: string;
}) {
  const inner = (
    <>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-surface text-ink-2 shadow-edge-neutral transition-[color,border-color,transform,box-shadow] duration-150 group-hover:-translate-y-0.5 group-hover:border-accent/40 group-hover:text-accent group-active:translate-y-[3px] group-active:shadow-pressed">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-ink">{title}</span>
        <span className="block truncate text-[13px] text-ink-3">{body}</span>
      </span>
      {href ? (
        <IconArrowUpRight size={16} className="shrink-0 text-ink-3 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
      ) : (
        <IconArrowRight size={16} className="shrink-0 text-ink-3 transition-transform group-hover:translate-x-0.5" />
      )}
    </>
  );
  const cls =
    "group flex w-full items-center gap-4 px-5 py-3.5 text-left transition-colors hover:bg-canvas sm:px-6 focus-visible:outline-offset-[-2px]";
  return href ? (
    <Link href={href} className={cls}>
      {inner}
    </Link>
  ) : (
    <button type="button" onClick={onClick} className={cls}>
      {inner}
    </button>
  );
}

export default function OverviewTab({ hospital, setTab }: { hospital: HospitalInfo; setTab: (t: Tab) => void }) {
  const [storage, setStorage] = useState<DatasetSummary | null | "failed">(null);
  const [network, setNetwork] = useState<NetworkStats | null | "failed">(null);
  const [activity, setActivity] = useState<ActivityEntry[] | null | "failed">(null);

  useEffect(() => {
    apiFetch<DatasetSummary>("/api/datasets/summary").then(setStorage).catch(() => setStorage("failed"));
    // The list endpoints return one page (50 rows), so counting their rows
    // stops being true once the network outgrows a page. The stats endpoint
    // counts in the database.
    apiFetch<NetworkStats>("/api/network/stats").then(setNetwork).catch(() => setNetwork("failed"));
    apiFetch<ActivityEntry[]>("/api/auth/activity?limit=8").then(setActivity).catch(() => setActivity("failed"));
  }, []);

  const loadingValue = <span className="skeleton inline-block h-7 w-12 align-middle" aria-label="Loading" />;
  const networkValue = (pick: (n: NetworkStats) => number) =>
    network === null ? loadingValue : network === "failed" ? "n/a" : pick(network).toLocaleString();

  const storageValue = (pick: (s: DatasetSummary) => string) =>
    storage === null ? loadingValue : storage === "failed" ? "n/a" : pick(storage);

  const stats = [
    { label: "Local images", value: storageValue((s) => s.images.toLocaleString()), hint: "Stored on this node" },
    {
      label: "Storage used",
      value: storageValue((s) => formatBytes(s.total_bytes)),
      hint:
        storage && storage !== "failed" && storage.quota > 0
          ? `${storage.images.toLocaleString()} of ${storage.quota.toLocaleString()} image quota`
          : "Of your image quota",
    },
    { label: "Network models", value: networkValue((n) => n.models), hint: "Published globally" },
    { label: "Network hospitals", value: networkValue((n) => n.hospitals), hint: "Verified nodes" },
  ];

  return (
    <div className="space-y-6">
      <SectionHeader
        title={hospital.name}
        description={
          hospital.location
            ? `${hospital.location}. A summary of your node and the federated network.`
            : "A summary of your node and the federated network."
        }
      />

      <StatStrip stats={stats} />

      <div className="grid gap-6 xl:grid-cols-[1fr_1.15fr]">
        <Panel className="overflow-hidden">
          <PanelHeader title="Quick actions" description="The usual next steps for a hospital node." />
          <div className="mt-4 divide-y divide-line border-t border-line">
            <ActionRow
              icon={<IconUpload size={16} />}
              title="Upload a dataset"
              body="Add wound images to your local store"
              onClick={() => setTab("data")}
            />
            <ActionRow
              icon={<IconScan size={16} />}
              title="Diagnose a wound"
              body="Classify one image or a batch of up to 10"
              onClick={() => setTab("predict")}
            />
            <ActionRow
              icon={<IconPulse size={16} />}
              title="Start federated training"
              body="Run a training round across the network"
              onClick={() => setTab("training")}
            />
            <ActionRow
              icon={<IconChip size={16} />}
              title="Browse models"
              body="See every model the network has published"
              href="/models"
            />
          </div>
        </Panel>

        <Panel>
          <PanelHeader
            title="Recent account activity"
            description="Sign-ins, uploads and deletions on your account. If something looks unfamiliar, change your password."
          />
          <PanelBody>
            {activity === null ? (
              <ul className="space-y-3" aria-busy="true" aria-label="Loading activity">
                {[0, 1, 2, 3].map((i) => (
                  <li key={i} className="flex justify-between gap-4">
                    <span className="skeleton h-4 w-40" />
                    <span className="skeleton h-4 w-28" />
                  </li>
                ))}
              </ul>
            ) : activity === "failed" ? (
              <EmptyState icon={<IconHistory size={18} />} title="Activity unavailable">
                Your recent activity could not be loaded. Reload the page to try again.
              </EmptyState>
            ) : activity.length === 0 ? (
              <EmptyState icon={<IconHistory size={18} />} title="No activity yet">
                Sign-ins and changes to your account will be listed here.
              </EmptyState>
            ) : (
              <ol className="relative space-y-0">
                {activity.map((e, i) => (
                  <li key={`${e.ts}-${i}`} className="relative flex gap-4 pb-4 last:pb-0">
                    {i < activity.length - 1 && (
                      <span aria-hidden="true" className="absolute left-[5px] top-4 bottom-0 w-px bg-line" />
                    )}
                    <span
                      aria-hidden="true"
                      className={`mt-1.5 h-[11px] w-[11px] shrink-0 rounded-full border-2 ${
                        i === 0 ? "border-accent bg-accent-soft" : "border-line-strong bg-surface"
                      }`}
                    />
                    <div className="flex min-w-0 flex-1 flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                      <span className="text-sm text-ink first-letter:uppercase">
                        {e.action.replace(/_/g, " ")}
                        {activityDetail(e) && <span className="text-ink-3"> · {activityDetail(e)}</span>}
                      </span>
                      <time dateTime={e.ts} className="shrink-0 font-mono text-xs text-ink-3 tabular">
                        {new Date(e.ts).toLocaleString()}
                      </time>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
