"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { apiFetch } from "@/lib/api";
import type { HospitalInfo } from "@/lib/types";

interface Props {
  hospital: HospitalInfo;
  onProfileUpdated: (hospital: HospitalInfo) => void;
}

const inputClass =
  "w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500/60";

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
    <form onSubmit={save} className="glass rounded-xl p-6 space-y-4">
      <div>
        <h3 className="font-semibold">Hospital profile</h3>
        <p className="text-xs text-zinc-500 mt-1">
          Shown to other hospitals in the network directory. Your sign-in email ({hospital.email})
          can&apos;t be changed here.
        </p>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="profile-name" className="block text-xs text-zinc-500 mb-1">
            Hospital name
          </label>
          <input
            id="profile-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={200}
            required
            autoComplete="organization"
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="profile-location" className="block text-xs text-zinc-500 mb-1">
            Location
          </label>
          <input
            id="profile-location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            maxLength={200}
            autoComplete="address-level2"
            className={inputClass}
          />
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button
          type="submit"
          disabled={saving || unchanged || !name.trim()}
          className="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 font-medium transition-colors"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
        {message && (
          <span role="status" className={`text-sm ${isError ? "text-rose-400" : "text-emerald-400"}`}>
            {message}
          </span>
        )}
      </div>
    </form>
  );
}

function endSessionLocally(router: ReturnType<typeof useRouter>) {
  try {
    localStorage.removeItem("hospital");
  } catch {
    // storage blocked — nothing cached to clear
  }
  router.push("/login");
}

function PasswordForm() {
  const router = useRouter();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
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
    <form onSubmit={save} className="glass rounded-xl p-6 space-y-4">
      <div>
        <h3 className="font-semibold">Change password</h3>
        <p className="text-xs text-zinc-500 mt-1">
          You&apos;ll be signed out everywhere and asked to sign in with the new password. At least
          8 characters.
        </p>
      </div>
      <div className="grid sm:grid-cols-3 gap-4">
        <div>
          <label htmlFor="pw-current" className="block text-xs text-zinc-500 mb-1">
            Current password
          </label>
          <input
            id="pw-current"
            type="password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
            autoComplete="current-password"
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="pw-new" className="block text-xs text-zinc-500 mb-1">
            New password
          </label>
          <input
            id="pw-new"
            type="password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="pw-confirm" className="block text-xs text-zinc-500 mb-1">
            Confirm new password
          </label>
          <input
            id="pw-confirm"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            className={inputClass}
          />
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 font-medium transition-colors"
        >
          {saving ? "Updating…" : "Update password"}
        </button>
        {error && (
          <span role="alert" className="text-sm text-rose-400">
            {error}
          </span>
        )}
      </div>
    </form>
  );
}

function SignOutEverywhere() {
  const router = useRouter();
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  async function signOutEverywhere() {
    if (!window.confirm("Sign out of every device, including this one?")) return;
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
    <div className="glass rounded-xl p-6 space-y-3">
      <div>
        <h3 className="font-semibold">Sign out everywhere</h3>
        <p className="text-xs text-zinc-500 mt-1">
          Ends every active session on every device — use it after losing a laptop or signing in on
          a shared computer. You can sign straight back in here.
        </p>
      </div>
      <div className="flex items-center gap-4">
        <button
          onClick={signOutEverywhere}
          disabled={working}
          className="px-4 py-2 text-sm rounded-lg bg-rose-600/10 border border-rose-500/30 text-rose-300 hover:bg-rose-600/20 disabled:opacity-40 transition-colors"
        >
          {working ? "Signing out…" : "Sign out of all devices"}
        </button>
        {error && (
          <span role="alert" className="text-sm text-rose-400">
            {error}
          </span>
        )}
      </div>
    </div>
  );
}

export default function SettingsTab(props: Props) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-8 max-w-3xl">
      <ProfileForm {...props} />
      <PasswordForm />
      <SignOutEverywhere />
    </motion.div>
  );
}
