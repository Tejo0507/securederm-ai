"use client";

import { useEffect, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch, ApiError } from "@/lib/api";
import { useCapsLock } from "@/lib/useCapsLock";
import AuthShell from "@/components/AuthShell";
import Button from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import PasswordInput from "@/components/ui/PasswordInput";
import Notice from "@/components/ui/Notice";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const { capsLock, handlers: capsHandlers } = useCapsLock();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [needsVerification, setNeedsVerification] = useState(false);
  const [resendState, setResendState] = useState<"idle" | "sending" | "sent">("idle");

  // Sent here because the session ended (expired, or signed out elsewhere):
  // say so, rather than showing a bare login form with no explanation.
  const [sessionEnded, setSessionEnded] = useState<string | null>(null);
  useEffect(() => {
    const reason = new URLSearchParams(window.location.search).get("reason");
    if (reason === "expired") setSessionEnded("Your session has ended. Please sign in again to continue.");
    else if (reason === "idle") {
      setSessionEnded("You were signed out after a period of inactivity. Please sign in again.");
    }
  }, []);

  // Someone who already has a valid session shouldn't be asked to sign in again.
  useEffect(() => {
    let cancelled = false;
    apiFetch("/api/auth/me")
      .then(() => !cancelled && router.replace("/dashboard"))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setNeedsVerification(false);
    setLoading(true);
    try {
      const hospital = await apiFetch<{ id: number; name: string }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      // Session lives in an httpOnly cookie now; this is just non-sensitive
      // display data cached for the dashboard's first paint.
      localStorage.setItem("hospital", JSON.stringify(hospital));
      router.push("/dashboard");
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 403) {
        setNeedsVerification(true);
      }
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setResendState("sending");
    try {
      const result = await apiFetch<{ dev_verification_token: string | null }>(
        "/api/auth/resend-verification",
        { method: "POST", body: JSON.stringify({ email }) },
      );
      if (result.dev_verification_token) {
        router.push(`/verify-email?token=${encodeURIComponent(result.dev_verification_token)}`);
        return;
      }
      setResendState("sent");
    } catch {
      setResendState("idle");
    }
  }

  return (
    <AuthShell
      title="Sign in"
      subtitle="Access your hospital's node, datasets and diagnosis history."
      footer={
        <>
          New to the network?{" "}
          <Link href="/signup" className="font-medium text-accent-ink underline-offset-4 hover:underline">
            Register your hospital
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate={false}>
        {sessionEnded && !error && (
          <Notice tone="warning" role="status">
            {sessionEnded}
          </Notice>
        )}
        {error && (
          <Notice tone="danger" role="alert">
            <p>{error}</p>
            {needsVerification && (
              <button
                type="button"
                onClick={handleResend}
                disabled={resendState !== "idle"}
                className="mt-1.5 font-medium underline underline-offset-4 disabled:no-underline disabled:opacity-70"
              >
                {resendState === "sending"
                  ? "Sending..."
                  : resendState === "sent"
                    ? "Verification email sent"
                    : "Resend verification email"}
              </button>
            )}
          </Notice>
        )}

        <Field label="Work email" htmlFor="login-email">
          <Input
            id="login-email"
            autoComplete="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="doctor@hospital.org"
          />
        </Field>

        <Field
          label="Password"
          htmlFor="login-password"
          hint={
            capsLock ? (
              <span role="status" className="text-warn-ink">
                Caps Lock is on.
              </span>
            ) : undefined
          }
        >
          <PasswordInput
            id="login-password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            visible={showPassword}
            onToggle={() => setShowPassword((s) => !s)}
            {...capsHandlers}
          />
        </Field>

        <Button type="submit" size="lg" loading={loading} className="w-full">
          {loading ? "Signing in..." : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}
