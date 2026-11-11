"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { assessPassword, MIN_PASSWORD_LENGTH } from "@/lib/password";
import PasswordStrength from "@/components/PasswordStrength";
import { useCapsLock } from "@/lib/useCapsLock";
import AuthShell from "@/components/AuthShell";
import Button, { buttonClass } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import PasswordInput from "@/components/ui/PasswordInput";
import Notice from "@/components/ui/Notice";
import { IconCheck } from "@/components/ui/icons";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
    location: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);

  function update(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const passwordsMismatch = form.confirmPassword.length > 0 && form.password !== form.confirmPassword;
  // Details the password should not echo back.
  const personal = [form.name, form.email.split("@")[0]];
  const { capsLock, handlers: capsHandlers } = useCapsLock();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    const strength = assessPassword(form.password, personal);
    if (strength.blocked) {
      setError(strength.advice || `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const result = await apiFetch<{
        status: string;
        email: string;
        dev_verification_token: string | null;
      }>("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          email: form.email,
          password: form.password,
          location: form.location,
        }),
      });

      if (result.dev_verification_token) {
        // No SMTP configured on the backend (local dev): skip straight to the
        // verification page instead of making the demo depend on a real inbox.
        router.push(`/verify-email?token=${encodeURIComponent(result.dev_verification_token)}`);
        return;
      }
      setSentTo(result.email);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  if (sentTo) {
    return (
      <AuthShell
        title="Check your inbox"
        subtitle={
          <>
            We sent a verification link to <span className="font-medium text-ink">{sentTo}</span>. Open it to
            activate your hospital account.
          </>
        }
      >
        <div className="flex items-center gap-3 rounded-lg border border-line bg-surface p-4 shadow-raise">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent-ink">
            <IconCheck size={18} />
          </span>
          <p className="text-[13px] leading-relaxed text-ink-2">
            The link works once. If it does not arrive within a few minutes, check your spam folder or
            request a new one from the sign-in page.
          </p>
        </div>
        <Link href="/login" className={buttonClass("secondary", "lg", "mt-6 w-full")}>
          Back to sign in
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Register your hospital"
      subtitle="Create a node to join the federated network. Your images stay on your own infrastructure."
      footer={
        <>
          Already registered?{" "}
          <Link href="/login" className="font-medium text-accent-ink underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <Notice tone="danger" role="alert">
            {error}
          </Notice>
        )}

        <Field label="Hospital name" htmlFor="signup-name">
          <Input
            type="text"
            required
            id="signup-name"
            autoComplete="organization"
            value={form.name}
            maxLength={200}
            onChange={(e) => update("name", e.target.value)}
            placeholder="City General Hospital"
          />
        </Field>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Work email" htmlFor="signup-email">
            <Input
              type="email"
              required
              id="signup-email"
              autoComplete="email"
              value={form.email}
              onChange={(e) => update("email", e.target.value)}
              placeholder="admin@hospital.org"
            />
          </Field>
          <Field label="Location" htmlFor="signup-location" aside={<span className="text-xs text-ink-3">Optional</span>}>
            <Input
              type="text"
              id="signup-location"
              autoComplete="address-level2"
              value={form.location}
              maxLength={200}
              onChange={(e) => update("location", e.target.value)}
              placeholder="San Francisco, CA"
            />
          </Field>
        </div>

        <Field label="Password" htmlFor="signup-password">
          <PasswordInput
            required
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={200}
            id="signup-password"
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            aria-describedby="signup-password-hint"
            visible={showPassword}
            onToggle={() => setShowPassword((s) => !s)}
            toggleLabel={["Show passwords", "Hide passwords"]}
            {...capsHandlers}
          />
          {capsLock && (
            <p role="status" className="mt-1.5 text-xs text-warn-ink">
              Caps Lock is on.
            </p>
          )}
          {form.password.length === 0 ? (
            <p id="signup-password-hint" className="mt-1.5 text-xs text-ink-3">
              At least {MIN_PASSWORD_LENGTH} characters. A short phrase works well.
            </p>
          ) : (
            <PasswordStrength id="signup-password-hint" password={form.password} personal={personal} />
          )}
        </Field>

        <Field
          label="Confirm password"
          htmlFor="signup-confirm"
          error={passwordsMismatch ? "Passwords do not match." : undefined}
        >
          <Input
            type={showPassword ? "text" : "password"}
            required
            id="signup-confirm"
            autoComplete="new-password"
            value={form.confirmPassword}
            onChange={(e) => update("confirmPassword", e.target.value)}
            aria-invalid={passwordsMismatch || undefined}
          />
        </Field>

        <Button type="submit" size="lg" loading={loading} disabled={passwordsMismatch} className="w-full">
          {loading ? "Creating account..." : "Create hospital account"}
        </Button>
      </form>
    </AuthShell>
  );
}
