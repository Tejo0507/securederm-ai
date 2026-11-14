"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import type { HospitalInfo } from "@/lib/types";
import { expectSessionEnd, onSessionEnded, SESSION_ENDED_REDIRECT } from "@/lib/session";
import { useIdleTimeout } from "@/lib/useIdleTimeout";
import { useDocumentTitle } from "@/lib/useDocumentTitle";
import IdleWarning from "@/components/IdleWarning";
import ThemeSwitch from "@/components/ThemeSwitch";
import TabBar, { panelId, tabId, type TabDef } from "@/components/dashboard/TabBar";
import OverviewTab from "@/components/dashboard/OverviewTab";
import DataTab from "@/components/dashboard/DataTab";
import PredictTab from "@/components/dashboard/PredictTab";
import HistoryTab from "@/components/dashboard/HistoryTab";
import TrainingTab from "@/components/dashboard/TrainingTab";
import NetworkTab from "@/components/dashboard/NetworkTab";
import SettingsTab from "@/components/dashboard/SettingsTab";
import { TAB_KEYS, type Tab } from "@/components/dashboard/tabs";
import Logo from "@/components/ui/Logo";
import Spinner from "@/components/ui/Spinner";
import {
  IconDatabase,
  IconHistory,
  IconLock,
  IconLogout,
  IconNetwork,
  IconOverview,
  IconPulse,
  IconScan,
  IconSettings,
} from "@/components/ui/icons";

// Minutes of inactivity before sign-out (0 turns it off). Override per deployment
// with NEXT_PUBLIC_IDLE_TIMEOUT_MINUTES.
const IDLE_MINUTES = Number(process.env.NEXT_PUBLIC_IDLE_TIMEOUT_MINUTES ?? 15);
const IDLE_TIMEOUT_MS = Number.isFinite(IDLE_MINUTES) ? Math.max(0, IDLE_MINUTES) * 60_000 : 0;

const TABS: TabDef<Tab>[] = [
  { key: "overview", label: "Overview", icon: <IconOverview size={16} /> },
  { key: "data", label: "Datasets", icon: <IconDatabase size={16} /> },
  { key: "predict", label: "Diagnose", icon: <IconScan size={16} /> },
  { key: "history", label: "History", icon: <IconHistory size={16} /> },
  { key: "training", label: "Training", icon: <IconPulse size={16} /> },
  { key: "network", label: "Network", icon: <IconNetwork size={16} /> },
  { key: "settings", label: "Settings", icon: <IconSettings size={16} /> },
];

export default function DashboardPage() {
  const router = useRouter();
  const [tab, setTabState] = useState<Tab>("overview");

  // Keep the section in the URL (#history) so a refresh or a shared link lands
  // on the same tab. replaceState: tab switches shouldn't flood the back button.
  const setTab = useCallback((next: Tab) => {
    setTabState(next);
    window.history.replaceState(null, "", `#${next}`);
  }, []);
  useEffect(() => {
    // Also reacts to the hash changing while the page stays open (a pasted
    // link in the same tab, or the browser's back/forward buttons).
    const syncFromHash = () => {
      const fromHash = window.location.hash.slice(1);
      setTabState(TAB_KEYS.includes(fromHash as Tab) ? (fromHash as Tab) : "overview");
    };
    syncFromHash();
    window.addEventListener("hashchange", syncFromHash);
    return () => window.removeEventListener("hashchange", syncFromHash);
  }, []);

  // Name the open section in the tab title, so several dashboard tabs (or
  // browser history entries) can be told apart.
  useDocumentTitle(`${TABS.find((t) => t.key === tab)?.label ?? "Overview"} · Dashboard · SecureDerm AI`);
  const [hospital, setHospital] = useState<HospitalInfo | null>(null);

  /* Auth guard: the session lives in an httpOnly cookie, so we can't just
     check localStorage for a token. Ask the backend who (if anyone) the
     current cookie belongs to. */
  useEffect(() => {
    try {
      const stored = localStorage.getItem("hospital");
      if (stored) setHospital(JSON.parse(stored)); // optimistic first paint
    } catch {
      // corrupt/blocked cache: fall through to the authoritative /me check
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

  // One central reaction when any request finds the session gone (it expired,
  // or was ended from another device) instead of a cryptic error in each tab.
  useEffect(
    () =>
      onSessionEnded(() => {
        try {
          localStorage.removeItem("hospital");
        } catch {
          // storage blocked; nothing cached to clear
        }
        router.replace(SESSION_ENDED_REDIRECT);
      }),
    [router],
  );

  async function endSession(destination: string) {
    expectSessionEnd();
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } catch {
      // even if the network call fails, still clear local state and leave
    }
    try {
      localStorage.removeItem("hospital");
    } catch {
      // storage blocked; nothing cached to clear
    }
    router.replace(destination);
  }
  const logout = () => endSession("/");

  // Sign out an unattended workstation: patient data must not stay on screen.
  const idle = useIdleTimeout(
    hospital !== null && IDLE_TIMEOUT_MS > 0,
    IDLE_TIMEOUT_MS,
    Math.min(60_000, IDLE_TIMEOUT_MS / 2),
    () => endSession("/login?reason=idle"),
  );

  // Changing section from inside a tab (quick actions) should start at the top.
  const goTo = useCallback(
    (next: Tab) => {
      setTab(next);
      window.scrollTo({ top: 0 });
    },
    [setTab],
  );

  if (!hospital) {
    return (
      <div className="flex min-h-screen items-center justify-center" role="status">
        <Spinner size={20} className="text-ink-3" />
        <span className="sr-only">Loading your dashboard</span>
      </div>
    );
  }

  function profileUpdated(updated: HospitalInfo) {
    setHospital(updated);
    localStorage.setItem("hospital", JSON.stringify(updated));
  }

  const initials = hospital.name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-line bg-surface/90 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6">
          <Logo href="/" />
          <div className="flex min-w-0 items-center gap-1 sm:gap-3">
            <ThemeSwitch className="mr-1 shrink-0 sm:mr-0" />
            <span className="hidden h-6 w-px bg-line sm:block" aria-hidden="true" />
            <div className="flex min-w-0 items-center gap-2.5">
              <span
                aria-hidden="true"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-line-strong bg-sunken font-mono text-[11px] font-medium text-ink"
              >
                {initials || "H"}
              </span>
              <div className="hidden min-w-0 leading-tight sm:block">
                <p className="truncate text-[13px] font-medium text-ink">{hospital.name}</p>
                {hospital.email && <p className="truncate text-xs text-ink-3">{hospital.email}</p>}
              </div>
            </div>
            <span className="mx-1 hidden h-6 w-px bg-line sm:block" aria-hidden="true" />
            <button
              type="button"
              onClick={logout}
              className="inline-flex h-8 items-center gap-2 rounded px-2.5 text-[13px] font-medium text-ink-2 transition-colors hover:bg-ink/[0.06] hover:text-ink"
            >
              <IconLogout size={16} />
              <span className="hidden sm:inline">Sign out</span>
              <span className="sr-only sm:hidden">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <IdleWarning secondsLeft={idle.secondsLeft} onStay={idle.stay} onSignOut={() => endSession("/")} />

      <div className="mx-auto max-w-[1440px] lg:grid lg:grid-cols-[232px_minmax(0,1fr)]">
        <nav
          aria-label="Dashboard"
          className="sticky top-14 z-30 border-b border-line bg-canvas/90 backdrop-blur-md lg:h-[calc(100vh-3.5rem)] lg:border-b-0 lg:border-r lg:bg-transparent lg:px-4 lg:py-6 lg:backdrop-blur-none"
        >
          <p className="label-mono mb-3 hidden px-3 text-ink-3 lg:block">Workspace</p>
          <TabBar tabs={TABS} active={tab} onChange={setTab} />
          <div className="mt-8 hidden rounded-lg border border-line bg-surface p-4 lg:block">
            <p className="flex items-center gap-2 text-[13px] font-medium text-ink">
              <IconLock size={14} className="text-accent" />
              Private node
            </p>
            <p className="mt-1.5 text-xs leading-relaxed text-ink-3">
              Images you upload stay on this node. Only model updates join the network.
              {IDLE_TIMEOUT_MS > 0 && ` Auto sign-out after ${IDLE_MINUTES} min idle.`}
            </p>
          </div>
        </nav>

        <main id="main" className="min-w-0 px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
          <div
            key={tab}
            role="tabpanel"
            id={panelId(tab)}
            aria-labelledby={tabId(tab)}
            tabIndex={-1}
            className="mx-auto max-w-6xl animate-fade-up focus:outline-none"
          >
            {tab === "overview" && <OverviewTab hospital={hospital} setTab={goTo} />}
            {tab === "data" && <DataTab />}
            {tab === "predict" && <PredictTab />}
            {tab === "history" && <HistoryTab />}
            {tab === "training" && <TrainingTab />}
            {tab === "network" && <NetworkTab />}
            {tab === "settings" && <SettingsTab hospital={hospital} onProfileUpdated={profileUpdated} />}
          </div>
        </main>
      </div>
    </div>
  );
}
