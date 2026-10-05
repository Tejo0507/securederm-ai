"use client";

import Link from "next/link";

// Route-level error boundary: without one, any render error shows Next's
// bare default error page. Deliberately shows no error message — it can
// contain internal details — only a digest to quote when reporting it.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-md text-center glass rounded-2xl p-8">
        <h1 className="text-xl font-semibold mb-2 text-rose-400">
          Something went wrong
        </h1>
        <p className="text-sm text-zinc-400">
          An unexpected error occurred. You can try again, or head back home.
        </p>
        {error.digest && (
          <p className="mt-2 text-xs text-zinc-600">Reference: {error.digest}</p>
        )}
        <div className="mt-6 flex justify-center gap-4 text-sm">
          <button
            onClick={reset}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 transition-colors"
          >
            Try again
          </button>
          <Link
            href="/"
            className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
          >
            Home
          </Link>
        </div>
      </div>
    </div>
  );
}
