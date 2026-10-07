"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { apiFetch, ApiError } from "@/lib/api";

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    // Sessions live in an httpOnly cookie now (never localStorage), so
    // there is no "token" to read here any more — this was silently
    // always false, showing "Log in" to every visitor regardless of
    // whether they actually had a valid session. "hospital" is the
    // non-sensitive display cache the dashboard writes after a
    // successful login/signup/me check; good enough for a nav link
    // (worst case it's stale and /dashboard's own auth guard redirects).
    let cancelled = false;
    try {
      setLoggedIn(!!localStorage.getItem("hospital"));
    } catch {
      // storage blocked — rely on the session check below
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

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-[#09090b]/80 backdrop-blur-lg border-b border-white/5"
          : ""
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="text-lg font-bold tracking-tight">
          <span className="text-white">
            SecureDerm
          </span>
          <span className="text-zinc-500 ml-1 font-medium">AI</span>
        </Link>

        <div className="hidden md:flex items-center gap-8">
          <Link
            href="/#features"
            className="text-sm text-zinc-400 hover:text-white transition-colors"
          >
            Features
          </Link>
          <Link
            href="/#how-it-works"
            className="text-sm text-zinc-400 hover:text-white transition-colors"
          >
            How It Works
          </Link>
          <Link
            href="/models"
            className="text-sm text-zinc-400 hover:text-white transition-colors"
          >
            Models
          </Link>
          <Link
            href="/demo"
            className="text-sm text-zinc-400 hover:text-white transition-colors"
          >
            Demo
          </Link>
        </div>

        <div className="flex items-center gap-3">
          {loggedIn ? (
            <Link
              href="/dashboard"
              className="text-sm px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 transition-colors"
            >
              Dashboard
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="text-sm text-zinc-400 hover:text-white transition-colors"
              >
                Log in
              </Link>
              <Link
                href="/signup"
                className="text-sm px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 transition-colors"
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </div>
    </motion.nav>
  );
}
