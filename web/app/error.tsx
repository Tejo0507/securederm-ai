"use client";

import Link from "next/link";
import StatusPage from "@/components/StatusPage";
import { buttonClass } from "@/components/ui/Button";

// Route-level error boundary: without one, any render error shows Next's bare
// default error page. Deliberately shows no error message (it can contain
// internal details), only a digest to quote when reporting it.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <StatusPage
      code="Unexpected error"
      title="Something went wrong"
      actions={
        <>
          <button type="button" onClick={reset} className={buttonClass("primary")}>
            Try again
          </button>
          <Link href="/" className={buttonClass("secondary")}>
            Back to home
          </Link>
        </>
      }
    >
      <p>An unexpected error occurred. You can try again, or head back home.</p>
      {error.digest && (
        <p className="mt-4 inline-flex rounded border border-line bg-sunken px-2 py-1 font-mono text-xs text-ink-2">
          Reference {error.digest}
        </p>
      )}
    </StatusPage>
  );
}
