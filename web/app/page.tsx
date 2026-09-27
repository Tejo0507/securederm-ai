"use client";

import { useRef } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { motion, useInView } from "framer-motion";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const ThreeScene = dynamic(() => import("@/components/ThreeScene"), {
  ssr: false,
});

/* ------------------------------------------------------------------ */
/*  Reusable scroll-reveal wrapper                                     */
/* ------------------------------------------------------------------ */
function Reveal({
  children,
  className = "",
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 30 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Feature cards data                                                 */
/* ------------------------------------------------------------------ */
const features = [
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
    ),
    title: "Federated Learning",
    desc: "Train across hospital networks without moving sensitive patient data. Models travel — data stays local.",
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
    ),
    title: "Differential Privacy",
    desc: "Mathematically guaranteed privacy with calibrated noise injection. Meet HIPAA and GDPR standards effortlessly.",
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
    ),
    title: "Secure Aggregation",
    desc: "FedAvg aggregation with encrypted weight updates. The server never sees individual hospital gradients.",
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
    ),
    title: "Edge-Ready Deployment",
    desc: "Lightweight ResNet-18 classifier runs on hospital hardware. No cloud dependency required for inference.",
  },
];

/* ------------------------------------------------------------------ */
/*  How-it-works steps                                                 */
/* ------------------------------------------------------------------ */
const steps = [
  { num: "01", title: "Upload Local Data", desc: "Each hospital uploads wound images to their own secure node." },
  { num: "02", title: "Train Locally", desc: "The model trains on each hospital's data with differential privacy." },
  { num: "03", title: "Share Gradients", desc: "Only encrypted model updates leave the hospital — never raw data." },
  { num: "04", title: "Aggregate Globally", desc: "FedAvg merges all updates into an improved global model." },
  { num: "05", title: "Deploy & Benefit", desc: "Every hospital receives the improved model. The cycle repeats." },
];

/* ================================================================== */
/*  PAGE                                                               */
/* ================================================================== */
export default function Home() {
  return (
    <>
      <Navbar />

      {/* ──────────── HERO ──────────── */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
        <ThreeScene />
        {/* gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#09090b] pointer-events-none" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.08),transparent_70%)] pointer-events-none" />

        <div className="relative z-10 text-center px-6 max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
          >
            <span className="inline-block text-xs font-medium tracking-widest uppercase text-indigo-400 border border-indigo-500/30 rounded-full px-4 py-1.5 mb-6">
              Privacy-Preserving Medical AI
            </span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.35 }}
            className="text-5xl sm:text-7xl font-bold tracking-tight leading-[1.1]"
          >
            <span className="text-white">
              SecureDerm AI
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.5 }}
            className="mt-6 text-lg sm:text-xl text-zinc-400 max-w-2xl mx-auto"
          >
            Train medical AI collaboratively across hospitals without
            exposing patient data. Powered by federated learning &amp;
            differential privacy.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.65 }}
            className="mt-10 flex flex-wrap justify-center gap-4"
          >
            <Link
              href="/signup"
              className="px-8 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-sm font-medium shadow-lg shadow-indigo-500/25 transition-all hover:shadow-indigo-500/40"
            >
              Start Training
            </Link>
            <Link
              href="/demo"
              className="px-8 py-3 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 text-sm font-medium transition-all"
            >
              See Demo
            </Link>
          </motion.div>
        </div>

        {/* scroll hint */}
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
        >
          <div className="w-5 h-8 rounded-full border-2 border-zinc-600 flex items-start justify-center p-1">
            <div className="w-1 h-2 rounded-full bg-zinc-500" />
          </div>
        </motion.div>
      </section>

      {/* ──────────── PROBLEM ──────────── */}
      <section className="py-28 px-6">
        <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-16 items-center">
          <Reveal>
            <span className="text-sm font-medium text-rose-400 uppercase tracking-widest">
              The Problem
            </span>
            <h2 className="mt-4 text-3xl sm:text-4xl font-bold leading-tight">
              Medical AI demands data — but privacy forbids sharing it.
            </h2>
            <p className="mt-4 text-zinc-400 leading-relaxed">
              Hospitals hold valuable wound imaging data locked behind
              regulatory firewalls. Training a robust classifier requires
              diverse data from many institutions, yet HIPAA and GDPR make
              direct data pooling impossible.
            </p>
          </Reveal>

          <Reveal delay={0.15}>
            <div className="grid grid-cols-2 gap-4">
              {[
                { val: "10+", label: "Wound Classes" },
                { val: "2,940", label: "Training Images" },
                { val: "100%", label: "Data Stays Local" },
                { val: "ε-DP", label: "Privacy Guarantees" },
              ].map((s) => (
                <div
                  key={s.label}
                  className="glass rounded-2xl p-6 text-center"
                >
                  <div className="text-2xl font-bold text-white">
                    {s.val}
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">{s.label}</div>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* ──────────── SOLUTION DIAGRAM ──────────── */}
      <section className="py-28 px-6 bg-gradient-to-b from-[#09090b] via-[#0c0c12] to-[#09090b]">
        <div className="max-w-4xl mx-auto text-center">
          <Reveal>
            <span className="text-sm font-medium text-indigo-400 uppercase tracking-widest">
              The Solution
            </span>
            <h2 className="mt-4 text-3xl sm:text-4xl font-bold">
              Federated Learning — models travel, data stays.
            </h2>
          </Reveal>

          <Reveal delay={0.2}>
            <div className="mt-16 relative flex flex-col md:flex-row items-center justify-center gap-8 md:gap-4">
              {/* Hospital A */}
              <motion.div
                whileHover={{ scale: 1.05 }}
                className="glass rounded-2xl p-6 w-52 text-center glow-border"
              >
                <div className="text-3xl mb-2">🏥</div>
                <div className="font-semibold text-sm">Hospital A</div>
                <div className="text-xs text-zinc-500 mt-1">
                  Trains locally
                </div>
              </motion.div>

              {/* Arrow */}
              <div className="hidden md:flex items-center">
                <motion.div
                  animate={{ x: [0, 6, 0] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                  className="text-indigo-400 text-2xl"
                >
                  →
                </motion.div>
              </div>

              {/* Aggregator */}
              <motion.div
                whileHover={{ scale: 1.05 }}
                className="rounded-2xl p-8 w-56 text-center bg-gradient-to-br from-indigo-600/20 to-purple-600/20 border border-indigo-500/30 glow"
              >
                <div className="text-3xl mb-2">🔗</div>
                <div className="font-semibold">Aggregator</div>
                <div className="text-xs text-zinc-400 mt-1">
                  FedAvg merges updates
                </div>
              </motion.div>

              {/* Arrow */}
              <div className="hidden md:flex items-center">
                <motion.div
                  animate={{ x: [0, -6, 0] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                  className="text-indigo-400 text-2xl"
                >
                  ←
                </motion.div>
              </div>

              {/* Hospital B */}
              <motion.div
                whileHover={{ scale: 1.05 }}
                className="glass rounded-2xl p-6 w-52 text-center glow-border"
              >
                <div className="text-3xl mb-2">🏥</div>
                <div className="font-semibold text-sm">Hospital B</div>
                <div className="text-xs text-zinc-500 mt-1">
                  Trains locally
                </div>
              </motion.div>
            </div>
          </Reveal>

          <Reveal delay={0.35}>
            <p className="mt-10 text-zinc-500 max-w-xl mx-auto text-sm">
              Each hospital trains on its own data, then sends only encrypted
              weight updates. The aggregator merges them into a better global
              model — without ever seeing raw images.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ──────────── FEATURES ──────────── */}
      <section id="features" className="py-28 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal className="text-center mb-16">
            <span className="text-sm font-medium text-indigo-400 uppercase tracking-widest">
              Features
            </span>
            <h2 className="mt-4 text-3xl sm:text-4xl font-bold">
              Built for security-first medical AI
            </h2>
          </Reveal>

          <div className="grid sm:grid-cols-2 gap-6">
            {features.map((f, i) => (
              <Reveal key={f.title} delay={i * 0.1}>
                <motion.div
                  whileHover={{ y: -4 }}
                  className="glass rounded-2xl p-8 h-full transition-all hover:glow-border"
                >
                  <div className="text-indigo-400 mb-4">{f.icon}</div>
                  <h3 className="text-lg font-semibold">{f.title}</h3>
                  <p className="mt-2 text-sm text-zinc-400 leading-relaxed">
                    {f.desc}
                  </p>
                </motion.div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ──────────── HOW IT WORKS ──────────── */}
      <section
        id="how-it-works"
        className="py-28 px-6 bg-gradient-to-b from-[#09090b] via-[#0c0c12] to-[#09090b]"
      >
        <div className="max-w-3xl mx-auto">
          <Reveal className="text-center mb-16">
            <span className="text-sm font-medium text-indigo-400 uppercase tracking-widest">
              How It Works
            </span>
            <h2 className="mt-4 text-3xl sm:text-4xl font-bold">
              Five steps to collaborative AI
            </h2>
          </Reveal>

          <div className="relative">
            {/* timeline line */}
            <div className="absolute left-6 top-0 bottom-0 w-px bg-gradient-to-b from-indigo-500/50 via-purple-500/30 to-transparent" />

            {steps.map((s, i) => (
              <Reveal key={s.num} delay={i * 0.08}>
                <div className="flex gap-6 mb-10 last:mb-0">
                  <div className="relative z-10 flex items-center justify-center w-12 h-12 rounded-full bg-indigo-600/20 border border-indigo-500/40 text-xs font-bold text-indigo-300 shrink-0">
                    {s.num}
                  </div>
                  <div className="pt-2">
                    <h3 className="font-semibold">{s.title}</h3>
                    <p className="mt-1 text-sm text-zinc-400">{s.desc}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ──────────── CTA ──────────── */}
      <section className="py-28 px-6">
        <Reveal className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl sm:text-5xl font-bold leading-tight">
            Ready to train{" "}
            <span className="text-indigo-400">privacy-preserving AI</span>?
          </h2>
          <p className="mt-4 text-zinc-400">
            Join the SecureDerm network. No data leaves your hospital.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <Link
              href="/signup"
              className="px-8 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-sm font-medium shadow-lg shadow-indigo-500/25 transition-all hover:shadow-indigo-500/40"
            >
              Create Hospital Account
            </Link>
            <Link
              href="/demo"
              className="px-8 py-3 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 text-sm font-medium transition-all"
            >
              Try the Demo
            </Link>
          </div>
        </Reveal>
      </section>

      <Footer />
    </>
  );
}
