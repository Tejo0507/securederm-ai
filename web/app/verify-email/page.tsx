"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { apiFetch } from "@/lib/api";

type Status = "verifying" | "success" | "error";

function VerifyEmailInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<Status>("verifying");
  const [error, setError] = useState("");

  // Verification tokens are single-use. React strict mode runs effects
  // twice in dev, and the second request would hit the now-consumed token
  // and overwrite the success state with an error.
  const submittedToken = useRef<string | null>(null);

  useEffect(() => {
    if (token && submittedToken.current === token) return;
    submittedToken.current = token;

    if (!token) {
      setStatus("error");
      setError("Missing verification token.");
      return;
    }

    apiFetch<{ id: number; name: string; email: string }>("/api/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .then((hospital) => {
        localStorage.setItem("hospital", JSON.stringify(hospital));
        setStatus("success");
        setTimeout(() => router.push("/dashboard"), 1200);
      })
      .catch((err: unknown) => {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Verification failed.");
      });
    // Only run once per mount — re-running on every `router` identity
    // change would re-submit an already-consumed, now-invalid token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md text-center glass rounded-2xl p-8"
      >
        {status === "verifying" && (
          <p className="text-sm text-zinc-400">Verifying your email...</p>
        )}
        {status === "success" && (
          <>
            <h1 className="text-xl font-semibold mb-2 text-emerald-400">Email verified</h1>
            <p className="text-sm text-zinc-400">Taking you to your dashboard...</p>
          </>
        )}
        {status === "error" && (
          <>
            <h1 className="text-xl font-semibold mb-2 text-rose-400">Verification failed</h1>
            <p className="text-sm text-zinc-400">{error}</p>
            <Link
              href="/login"
              className="inline-block mt-6 text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              Back to sign in
            </Link>
          </>
        )}
      </motion.div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailInner />
    </Suspense>
  );
}
