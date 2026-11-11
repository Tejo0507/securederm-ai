"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import AuthShell from "@/components/AuthShell";
import { buttonClass } from "@/components/ui/Button";
import Notice from "@/components/ui/Notice";
import Spinner from "@/components/ui/Spinner";

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
    // Only run once per mount: re-running on every `router` identity change
    // would re-submit an already-consumed, now-invalid token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (status === "verifying") {
    return (
      <AuthShell title="Verifying your email" subtitle="This only takes a moment.">
        <div role="status" className="flex items-center gap-3 text-sm text-ink-2">
          <Spinner size={16} className="text-accent" />
          Checking your verification link...
        </div>
      </AuthShell>
    );
  }

  if (status === "success") {
    return (
      <AuthShell title="Email verified" subtitle="Your hospital account is active.">
        <Notice tone="success" role="status">
          Taking you to your dashboard...
        </Notice>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Verification failed" subtitle="This link could not be used to activate an account.">
      <Notice tone="danger" role="alert">
        {error}
      </Notice>
      <p className="mt-4 text-[13px] leading-relaxed text-ink-2">
        Each link works once. Sign in with your email and password to request a new one.
      </p>
      <Link href="/login" className={buttonClass("secondary", "lg", "mt-6 w-full")}>
        Back to sign in
      </Link>
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailInner />
    </Suspense>
  );
}
