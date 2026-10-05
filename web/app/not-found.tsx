import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-md text-center glass rounded-2xl p-8">
        <h1 className="text-xl font-semibold mb-2">Page not found</h1>
        <p className="text-sm text-zinc-400">
          The page you were looking for doesn&apos;t exist.
        </p>
        <Link
          href="/"
          className="inline-block mt-6 text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
        >
          Back to home
        </Link>
      </div>
    </div>
  );
}
