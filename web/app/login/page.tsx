"use client";

import { useEffect, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { apiFetch, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [needsVerification, setNeedsVerification] = useState(false);
  const [resendState, setResendState] = useState<"idle" | "sending" | "sent">("idle");

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
      const hospital = await apiFetch<{ id: number; name: string }>(
        "/api/auth/login",
        {
          method: "POST",
          body: JSON.stringify({ email, password }),
        },
      );
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
    <div className="min-h-screen flex items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="text-center mb-8">
          <Link href="/" className="text-2xl font-bold">
            <span className="text-white">SecureDerm</span>
            <span className="text-zinc-500 ml-1">AI</span>
          </Link>
          <p className="mt-2 text-sm text-zinc-500">
            Sign in to your hospital account
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="glass rounded-2xl p-8 space-y-5"
        >
          {error && (
            <div className="text-sm text-rose-400 bg-rose-400/10 border border-rose-400/20 rounded-lg px-4 py-2 space-y-2">
              <p>{error}</p>
              {needsVerification && (
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={resendState !== "idle"}
                  className="text-xs font-medium text-indigo-400 hover:text-indigo-300 disabled:opacity-50 transition-colors"
                >
                  {resendState === "sending"
                    ? "Sending..."
                    : resendState === "sent"
                      ? "Verification email sent"
                      : "Resend verification email"}
                </button>
              )}
            </div>
          )}

          <div>
            <label className="block text-sm text-zinc-400 mb-1.5">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
              placeholder="doctor@hospital.com"
            />
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1.5">
              Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 pr-16 rounded-lg bg-white/5 border border-white/10 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                tabIndex={-1}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm font-medium shadow-lg shadow-indigo-500/25 transition-all"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>

          <p className="text-center text-sm text-zinc-500">
            Don&apos;t have an account?{" "}
            <Link
              href="/signup"
              className="text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              Sign up
            </Link>
          </p>
        </form>
      </motion.div>
    </div>
  );
}
