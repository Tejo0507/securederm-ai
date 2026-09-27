import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-white/5 py-12 px-6">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">
            SecureDerm AI
          </span>
          <span className="text-xs text-zinc-600">
            &copy; {new Date().getFullYear()}
          </span>
        </div>
        <div className="flex items-center gap-6 text-sm text-zinc-500">
          <Link href="/models" className="hover:text-zinc-300 transition-colors">
            Models
          </Link>
          <Link href="/demo" className="hover:text-zinc-300 transition-colors">
            Demo
          </Link>
          <Link href="/dashboard" className="hover:text-zinc-300 transition-colors">
            Dashboard
          </Link>
        </div>
      </div>
    </footer>
  );
}
