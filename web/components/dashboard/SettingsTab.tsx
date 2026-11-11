"use client";

import { FormEvent, ReactNode, useState } from "react";
import { useRouter } from "next/navigation";
import { apiDownload, apiFetch } from "@/lib/api";
import { expectSessionEnd } from "@/lib/session";
import { useConfirm } from "@/components/ConfirmProvider";
import PasswordStrength from "@/components/PasswordStrength";
import SectionHeader from "@/components/dashboard/SectionHeader";
import { Panel } from "@/components/ui/Panel";
import Button from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { InlineStatus } from "@/components/ui/Notice";
import { IconDownload, IconLogout } from "@/components/ui/icons";
import { assessPassword } from "@/lib/password";
import type { HospitalInfo } from "@/lib/types";

interface Props {
  hospital: HospitalInfo;
  onProfileUpdated: (hospital: HospitalInfo) => void;
}

/**
 * One settings block: title and explanation on the left, controls on the right
 * (stacked on narrow screens). Every block on the page uses this frame.
 */
function SettingsBlock({
  title,
  description,
  children,
  footer,
  tone = "default",
  onSubmit,
}: {
  title: string;
  description: ReactNode;
  children?: ReactNode;
  footer: ReactNode;
  tone?: "default" | "danger";
  onSubmit?: (e: FormEvent<HTMLFormElement>) => void;
}) {
  const body = (
    <>
      <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[minmax(0,260px)_1fr] lg:gap-10">
        <div>
          <h2 className={`text-[15px] font-semibold tracking-[-0.01em] ${tone === "danger" ? "text-danger-ink" : "text-ink"}`}>
            {title}
          </h2>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{description}</p>
        </div>
        {children && <div className="min-w-0">{children}</div>}
      </div>
      <div
        className={`flex flex-wrap items-center justify-end gap-3 border-t px-5 py-3 sm:px-6 ${
          tone === "danger" ? "border-danger/20 bg-danger-soft/40" : "border-line bg-canvas/60"
        }`}
      >
        {footer}
      </div>
    </>
  );

  if (onSubmit) {
    return (
      <Panel as="form" tone={tone} onSubmit={onSubmit as (e: FormEvent<HTMLElement>) => void} className="overflow-hidden">
        {body}
      </Panel>
    );
  }
  return (
    <Panel tone={tone} className="overflow-hidden">
      {body}
    </Panel>
  );
}

function ProfileForm({ hospital, onProfileUpdated }: Props) {
  const [name, setName] = useState(hospital.name);
  const [location, setLocation] = useState(hospital.location ?? "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [isError, setIsError] = useState(false);

  const unchanged = name.trim() === hospital.name && location.trim() === (hospital.location ?? "");

  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const updated = await apiFetch<HospitalInfo>("/api/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ name, location }),
      });
      onProfileUpdated(updated);
      setName(updated.name);
      setLocation(updated.location ?? "");
      setIsError(false);
      setMessage("Profile saved.");
    } catch (err: unknown) {
      setIsError(true);
      setMessage(err instanceof Error ? err.message : "Could not save profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <SettingsBlock
      title="Hospital profile"
      description={
        <>
          Shown to other hospitals in the network directory. Your sign-in email ({hospital.email}) can&apos;t be
          changed here.
        </>
      }
      onSubmit={save}
      footer={
        <>
          {message && <InlineStatus error={isError}>{message}</InlineStatus>}
          <Button type="submit" size="sm" loading={saving} disabled={unchanged || !name.trim()}>
            {saving ? "Saving..." : "Save changes"}
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Hospital name" htmlFor="profile-name">
          <Input
            id="profile-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={200}
            required
            autoComplete="organization"
          />
        </Field>
        <Field label="Location" htmlFor="profile-location">
          <Input
            id="profile-location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            maxLength={200}
            autoComplete="address-level2"
          />
        </Field>
      </div>
    </SettingsBlock>
  );
}

function endSessionLocally(router: ReturnType<typeof useRouter>) {
  expectSessionEnd(); // deliberate: later failed polls are not "session expired"
  try {
    localStorage.removeItem("hospital");
  } catch {
    // storage blocked; nothing cached to clear
  }
  router.push("/login");
}

function PasswordForm({ hospital }: { hospital: HospitalInfo }) {
  const router = useRouter();
  const personal = [hospital.name, (hospital.email ?? "").split("@")[0]];
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    const strength = assessPassword(next, personal);
    if (strength.blocked) {
      setError(strength.advice);
      return;
    }
    if (current && next === current) {
      setError("The new password must be different from the current one.");
      return;
    }
    if (next !== confirm) {
      setError("The new passwords don't match.");
      return;
    }
    setSaving(true);
    try {
      await apiFetch("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      // The server ended this session; sign in again with the new password.
      endSessionLocally(router);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not change password.");
      setSaving(false);
    }
  }

  return (
    <SettingsBlock
      title="Change password"
      description="You'll be signed out everywhere and asked to sign in with the new password. At least 8 characters."
      onSubmit={save}
      footer={
        <>
          {error && <InlineStatus error>{error}</InlineStatus>}
          <Button type="submit" size="sm" loading={saving}>
            {saving ? "Updating..." : "Update password"}
          </Button>
        </>
      }
    >
      <div className="grid max-w-md gap-4">
        <Field label="Current password" htmlFor="pw-current">
          <Input
            id="pw-current"
            type="password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
            autoComplete="current-password"
          />
        </Field>
        <div>
          <Field label="New password" htmlFor="pw-new">
            <Input
              id="pw-new"
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              aria-describedby="pw-new-hint"
            />
          </Field>
          <PasswordStrength id="pw-new-hint" password={next} personal={personal} />
        </div>
        <Field label="Confirm new password" htmlFor="pw-confirm">
          <Input
            id="pw-confirm"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
        </Field>
      </div>
    </SettingsBlock>
  );
}

function DownloadMyData() {
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [isError, setIsError] = useState(false);

  async function download() {
    setWorking(true);
    setMessage("");
    try {
      await apiDownload("/api/auth/export", "securederm-my-data.json");
      setIsError(false);
      setMessage("Download started.");
    } catch (err: unknown) {
      setIsError(true);
      setMessage(err instanceof Error ? err.message : "Could not export your data.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <SettingsBlock
      title="Download my data"
      description="A JSON copy of your profile, dataset records, prediction history and account activity. It never includes your password, session tokens or uploaded images."
      footer={
        <>
          {message && <InlineStatus error={isError}>{message}</InlineStatus>}
          <Button variant="secondary" size="sm" onClick={download} loading={working}>
            {!working && <IconDownload size={15} />}
            {working ? "Preparing..." : "Download JSON"}
          </Button>
        </>
      }
    />
  );
}

function SignOutEverywhere() {
  const confirm = useConfirm();
  const router = useRouter();
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  async function signOutEverywhere() {
    const ok = await confirm({
      title: "Sign out of every device?",
      message:
        "All active sessions on this account end, including this one. You can sign straight back in.",
      confirmLabel: "Sign out everywhere",
      danger: true,
    });
    if (!ok) return;
    setWorking(true);
    setError("");
    try {
      await apiFetch("/api/auth/logout-all", { method: "POST" });
      endSessionLocally(router);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not end your sessions.");
      setWorking(false);
    }
  }

  return (
    <SettingsBlock
      tone="danger"
      title="Sign out everywhere"
      description="Ends every active session on every device. Use it after losing a laptop or signing in on a shared computer. You can sign straight back in here."
      footer={
        <>
          {error && <InlineStatus error>{error}</InlineStatus>}
          <Button variant="danger-quiet" size="sm" onClick={signOutEverywhere} loading={working}>
            {!working && <IconLogout size={15} />}
            {working ? "Signing out..." : "Sign out of all devices"}
          </Button>
        </>
      }
    />
  );
}

export default function SettingsTab(props: Props) {
  return (
    <div className="max-w-4xl animate-fade-up">
      <SectionHeader title="Settings" description="Your hospital profile, password, data export and sessions." />
      <div className="space-y-6">
        <ProfileForm {...props} />
        <PasswordForm hospital={props.hospital} />
        <DownloadMyData />
        <SignOutEverywhere />
      </div>
    </div>
  );
}
