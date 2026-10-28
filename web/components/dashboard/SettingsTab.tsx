"use client";

import { FormEvent, useState } from "react";
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

export default function SettingsTab(props: Props) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-8 max-w-3xl">
      <ProfileForm {...props} />
    </motion.div>
  );
}
