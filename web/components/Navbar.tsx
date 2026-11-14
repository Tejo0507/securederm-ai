"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { apiFetch, ApiError, mightHaveSession } from "@/lib/api";
import Logo from "@/components/ui/Logo";
import { buttonClass } from "@/components/ui/Button";
import { IconArrowRight, IconMenu, IconX } from "@/components/ui/icons";

const LINKS = [
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#privacy", label: "Privacy" },
  { href: "/models", label: "Models" },
  { href: "/demo", label: "Demo" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    // Sessions live in an httpOnly cookie, so there is no token to read here.
    // "hospital" is the non-sensitive display cache the dashboard writes after
    // a successful login/signup/me check; good enough for a nav link (worst
    // case it's stale and /dashboard's own auth guard redirects).
    let cancelled = false;
    if (!mightHaveSession()) {
      // No session cookie pair: signed out for sure, and the cache is stale.
      try {
        localStorage.removeItem("hospital");
      } catch {
        // ignore
      }
      return () => window.removeEventListener("scroll", onScroll);
    }
    try {
      setLoggedIn(!!localStorage.getItem("hospital"));
    } catch {
      // storage blocked; rely on the session check below
    }
    // The cache can be stale (expired or revoked session); ask the backend.
    // Only a definitive 401 flips it to logged-out, so a network blip
    // doesn't make a signed-in user look signed out.
    apiFetch("/api/auth/me")
      .then(() => !cancelled && setLoggedIn(true))
      .catch((err: unknown) => {
        if (cancelled || !(err instanceof ApiError) || err.status !== 401) return;
        setLoggedIn(false);
        try {
          localStorage.removeItem("hospital");
        } catch {
          // ignore
        }
      });
    return () => {
      cancelled = true;
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  // Close the phone menu on navigation and on Escape.
  useEffect(() => setMenuOpen(false), [pathname]);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const isActive = (href: string) => !href.startsWith("/#") && pathname === href;

  return (
    <header
      className={`sticky top-0 z-50 border-b transition-[background-color,border-color] duration-200 ${
        menuOpen
          ? "border-line bg-canvas"
          : scrolled
            ? "border-line bg-canvas/85 backdrop-blur-md"
            : "border-transparent bg-canvas"
      }`}
    >
      <nav aria-label="Main" className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo />

        <ul className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                aria-current={isActive(l.href) ? "page" : undefined}
                className={`rounded px-3 py-2 text-sm transition-colors ${
                  isActive(l.href) ? "text-ink" : "text-ink-2 hover:text-ink"
                }`}
              >
                {l.label}
              </Link>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-2">
          {loggedIn ? (
            <Link href="/dashboard" className={buttonClass("primary", "sm", "hidden sm:inline-flex")}>
              Open dashboard
              <IconArrowRight size={14} />
            </Link>
          ) : (
            <>
              <Link href="/login" className={buttonClass("ghost", "sm", "hidden sm:inline-flex")}>
                Sign in
              </Link>
              <Link href="/signup" className={buttonClass("primary", "sm", "hidden sm:inline-flex")}>
                Register hospital
              </Link>
            </>
          )}
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            className="inline-flex h-9 w-9 items-center justify-center rounded text-ink hover:bg-ink/[0.06] md:hidden"
          >
            {menuOpen ? <IconX size={20} /> : <IconMenu size={20} />}
          </button>
        </div>
      </nav>

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            id="mobile-menu"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden border-t border-line md:hidden"
          >
            <ul className="mx-auto max-w-6xl px-4 py-3 sm:px-6">
              {LINKS.map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    onClick={() => setMenuOpen(false)}
                    aria-current={isActive(l.href) ? "page" : undefined}
                    className="flex items-center justify-between rounded px-2 py-3 text-[15px] text-ink hover:bg-ink/[0.04]"
                  >
                    {l.label}
                    <IconArrowRight size={16} className="text-ink-3" />
                  </Link>
                </li>
              ))}
            </ul>
            <div className="mx-auto grid max-w-6xl grid-cols-2 gap-2 border-t border-line px-4 py-4 sm:px-6">
              {loggedIn ? (
                <Link href="/dashboard" className={buttonClass("primary", "md", "col-span-2")}>
                  Open dashboard
                </Link>
              ) : (
                <>
                  <Link href="/login" className={buttonClass("secondary", "md")}>
                    Sign in
                  </Link>
                  <Link href="/signup" className={buttonClass("primary", "md")}>
                    Register
                  </Link>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
