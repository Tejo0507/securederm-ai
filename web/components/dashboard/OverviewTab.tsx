"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { HospitalInfo } from "@/lib/types";
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
  ip?: string;
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
  const [datasets, setDatasets] = useState<{ image_count: number }[] | null>(null);
  const [models, setModels] = useState<unknown[] | null>(null);
  const [hospitals, setHospitals] = useState<unknown[] | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[] | null>(null);

  useEffect(() => {
    apiFetch<{ image_count: number }[]>("/api/datasets").then(setDatasets).catch(() => setDatasets([]));
    apiFetch<unknown[]>("/api/models").then(setModels).catch(() => setModels([]));
    apiFetch<unknown[]>("/api/hospitals").then(setHospitals).catch(() => setHospitals([]));
    apiFetch<ActivityEntry[]>("/api/auth/activity?limit=8").then(setActivity).catch(() => setActivity([]));
  }, []);

  const totalImages = (datasets ?? []).reduce((sum, d) => sum + (d.image_count || 0), 0);
  const loadingValue = <span className="skeleton inline-block h-7 w-12 align-middle" aria-label="Loading" />;

  const stats = [
    { label: "Local images", value: datasets ? totalImages.toLocaleString() : loadingValue, hint: "Stored on this node" },
    { label: "Datasets", value: datasets ? String(datasets.length) : loadingValue, hint: "Upload batches" },
    { label: "Network models", value: models ? String(models.length) : loadingValue, hint: "Published globally" },
    { label: "Network hospitals", value: hospitals ? String(hospitals.length) : loadingValue, hint: "Registered nodes" },
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
                        {typeof e.images === "number" && (
                          <span className="text-ink-3"> · {e.images} images</span>
                        )}
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
