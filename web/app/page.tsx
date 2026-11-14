import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Reveal from "@/components/marketing/Reveal";
import Hero3D from "@/components/marketing/hero3d/Hero3D";
import { buttonClass } from "@/components/ui/Button";
import Tilt from "@/components/ui/Tilt";
import {
  IconArrowRight,
  IconCheck,
  IconChip,
  IconLock,
  IconMerge,
  IconShield,
  IconX,
} from "@/components/ui/icons";

const FIGURES = [
  { value: "10+", label: "wound classes" },
  { value: "2,940", label: "training images" },
  { value: "0", label: "images leave a site" },
  { value: "ε-DP", label: "on every update" },
];

const PROOF = [
  { icon: <IconMerge size={15} />, label: "FedAvg aggregation" },
  { icon: <IconShield size={15} />, label: "ε-differential privacy" },
  { icon: <IconChip size={15} />, label: "ResNet-18, on site" },
];

const CAPABILITIES = [
  {
    icon: <IconLock size={20} />,
    title: "Federated learning",
    body: "Train across a hospital network without moving patient data. The model travels to the data, never the other way round.",
  },
  {
    icon: <IconShield size={20} />,
    title: "Differential privacy",
    body: "Calibrated noise on every update gives a mathematical bound on what can be learned about any single patient, in line with HIPAA and GDPR expectations.",
  },
  {
    icon: <IconMerge size={20} />,
    title: "Secure aggregation",
    body: "FedAvg merges encrypted weight updates. The aggregator never sees an individual hospital's gradients.",
  },
  {
    icon: <IconChip size={20} />,
    title: "Runs on hospital hardware",
    body: "A lightweight ResNet-18 classifier serves predictions on site. Inference needs no cloud connection.",
  },
];

const STEPS = [
  { title: "Upload locally", body: "Each hospital adds wound images to its own secure node." },
  { title: "Train on site", body: "The model trains on that hospital's data with differential privacy." },
  { title: "Share updates", body: "Only encrypted model updates leave the building. Raw images never do." },
  { title: "Aggregate", body: "FedAvg merges every site's update into a better global model." },
  { title: "Redeploy", body: "Each hospital receives the improved model, and the cycle repeats." },
];

const STAYS = [
  "Wound images and their pixels",
  "Patient identifiers and records",
  "Unprotected per-image gradients",
];
const LEAVES = [
  "Clipped, noised weight updates",
  "Which sites took part in a round",
  "Aggregate training loss per round",
];

export default function Home() {
  return (
    <>
      <Navbar />
      <main id="main">
        {/* Hero */}
        <section className="relative overflow-hidden border-b border-line">
          {/* Engineering paper that fades out toward the copy, and a faint wash behind the model. */}
          <div
            aria-hidden="true"
            className="grid-paper absolute inset-0 [mask-image:radial-gradient(ellipse_70%_80%_at_75%_45%,black,transparent_75%)]"
          />
          <div
            aria-hidden="true"
            className="absolute -right-40 top-10 h-[640px] w-[760px] rounded-full bg-[radial-gradient(closest-side,rgb(var(--accent)/0.10),transparent)]"
          />
          <div className="relative mx-auto grid max-w-6xl items-center gap-10 px-4 pb-14 pt-10 sm:px-6 sm:pt-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.08fr)] lg:gap-12 lg:pb-20 lg:pt-16">
            <div className="animate-fade-up">
              <p className="label-mono inline-flex items-center gap-2 text-accent-ink">
                <span className="h-px w-6 bg-accent" />
                Federated learning for wound imaging
              </p>
              {/* Three short lines that never wrap mid-thought. The longest is ~8 font-sizes
                  wide, so each breakpoint's size is chosen to fit its column. */}
              <h1 className="mt-5 text-[2.5rem] font-semibold leading-[1.02] tracking-[-0.04em] text-ink sm:text-[3.5rem] lg:text-[3.25rem] xl:text-[3.75rem]">
                <span className="block">One wound model.</span>
                <span className="block">Every hospital.</span>
                <span className="block text-ink-3">No images shared.</span>
              </h1>
              <p className="mt-6 max-w-[34rem] text-[17px] leading-relaxed text-ink-2">
                SecureDerm AI lets hospital networks build a shared wound classifier. Each site trains on
                its own data behind its own firewall; only noised, encrypted weight updates travel to the
                aggregator.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link href="/signup" className={buttonClass("primary", "lg")}>
                  Register your hospital
                  <IconArrowRight size={16} />
                </Link>
                <Link href="/demo" className={buttonClass("secondary", "lg")}>
                  Watch a federated round
                </Link>
              </div>
              <ul className="mt-10 flex flex-wrap gap-x-6 gap-y-3 border-t border-line pt-6 text-[13px] text-ink-2">
                {PROOF.map((p) => (
                  <li key={p.label} className="flex items-center gap-2">
                    <span className="text-accent">{p.icon}</span>
                    {p.label}
                  </li>
                ))}
              </ul>
            </div>

            <div className="animate-fade-up [animation-delay:120ms]">
              <Hero3D />
            </div>
          </div>

          <dl className="border-t border-line bg-surface">
            <div className="mx-auto grid max-w-6xl grid-cols-2 px-4 sm:px-6 md:grid-cols-4">
              {FIGURES.map((f, i) => (
                <div
                  key={f.label}
                  className={`flex flex-col-reverse py-6 ${i % 2 === 1 ? "border-l border-line pl-5 sm:pl-6" : ""} ${
                    i >= 2 ? "border-t border-line md:border-t-0" : ""
                  } ${i === 2 ? "md:border-l md:pl-6" : ""}`}
                >
                  <dt className="mt-1 text-[13px] text-ink-3">{f.label}</dt>
                  <dd className="text-2xl font-semibold tracking-[-0.02em] text-ink tabular sm:text-3xl">
                    {f.value}
                  </dd>
                </div>
              ))}
            </div>
          </dl>
        </section>

        {/* The constraint */}
        <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:py-28">
          <div className="grid gap-10 lg:grid-cols-[1fr_1.1fr] lg:gap-20">
            <Reveal>
              <p className="label-mono text-ink-3">The constraint</p>
              <h2 className="mt-4 text-3xl font-semibold leading-[1.15] tracking-[-0.025em] text-ink sm:text-4xl">
                Medical AI needs data from many hospitals. Privacy law says that data cannot move.
              </h2>
            </Reveal>
            <Reveal delay={0.08} className="lg:pt-9">
              <p className="text-[17px] leading-relaxed text-ink-2">
                Hospitals hold valuable wound imaging locked behind regulatory firewalls. A robust
                classifier needs diverse images from many institutions, yet HIPAA and GDPR make pooling
                them in one place impractical.
              </p>
              <p className="mt-5 text-[17px] leading-relaxed text-ink-2">
                Federated learning turns the problem around. Instead of collecting images, SecureDerm
                sends the model to each hospital, lets it learn there, and combines only what it learned.
              </p>
            </Reveal>
          </div>
        </section>

        {/* How it works */}
        <section id="how-it-works" className="scroll-mt-20 border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:py-28">
            <Reveal className="max-w-2xl">
              <p className="label-mono text-ink-3">How it works</p>
              <h2 className="mt-4 text-3xl font-semibold tracking-[-0.025em] text-ink sm:text-4xl">
                Five steps per round. Repeated until the model is good enough.
              </h2>
            </Reveal>

            <ol className="relative mt-14 grid gap-8 lg:grid-cols-5 lg:gap-6">
              <span
                aria-hidden="true"
                className="absolute left-[15px] top-2 bottom-2 w-px bg-line-strong lg:left-0 lg:right-0 lg:top-[15px] lg:bottom-auto lg:h-px lg:w-auto"
              />
              {STEPS.map((s, i) => (
                <li key={s.title} className="relative">
                  <Reveal delay={i * 0.06} className="flex gap-5 lg:block">
                    <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-line-strong bg-surface font-mono text-xs font-medium text-ink shadow-edge-neutral">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div className="lg:mt-5">
                      <h3 className="text-[15px] font-semibold text-ink">{s.title}</h3>
                      <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{s.body}</p>
                    </div>
                  </Reveal>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Privacy boundary */}
        <section id="privacy" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6 lg:py-28">
          <Reveal className="max-w-2xl">
            <p className="label-mono text-ink-3">The privacy boundary</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.025em] text-ink sm:text-4xl">
              What crosses the hospital firewall, and what never does.
            </h2>
          </Reveal>

          <Reveal delay={0.08}>
            <Tilt max={2.5} className="mt-12 grid rounded-xl border border-line bg-surface shadow-slab md:grid-cols-2">
              <div className="p-6 sm:p-8">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink text-canvas">
                    <IconLock size={14} />
                  </span>
                  <h3 className="text-[15px] font-semibold text-ink">Stays inside the hospital</h3>
                </div>
                <ul className="mt-6 space-y-3.5">
                  {STAYS.map((item) => (
                    <li key={item} className="flex items-start gap-3 text-[15px] text-ink-2">
                      <IconX size={16} className="mt-0.5 shrink-0 text-ink-3" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              {/* Rounded to match the card: a tilting card can't clip with overflow-hidden. */}
              <div className="rounded-b-xl border-t border-line bg-canvas/50 p-6 sm:p-8 md:rounded-bl-none md:rounded-r-xl md:border-l md:border-t-0">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-accent-on">
                    <IconArrowRight size={14} />
                  </span>
                  <h3 className="text-[15px] font-semibold text-ink">Sent to the aggregator</h3>
                </div>
                <ul className="mt-6 space-y-3.5">
                  {LEAVES.map((item) => (
                    <li key={item} className="flex items-start gap-3 text-[15px] text-ink-2">
                      <IconCheck size={16} className="mt-0.5 shrink-0 text-accent" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </Tilt>
          </Reveal>

          {/* Separate slabs that tilt toward the pointer; the icon floats highest,
              the title a step below, the body on the face. */}
          <div className="mt-16 grid gap-5 sm:grid-cols-2">
            {CAPABILITIES.map((c, i) => (
              <Reveal key={c.title} delay={i * 0.05} className="h-full">
                <Tilt
                  as="article"
                  className="h-full rounded-xl border border-line bg-surface p-6 shadow-slab hover:shadow-lift sm:p-8"
                >
                  <div className="lift-2 flex items-center justify-between">
                    <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-accent/25 bg-accent-soft text-accent-ink shadow-edge-neutral">
                      {c.icon}
                    </span>
                    <span className="font-mono text-2xs text-ink-3">{String(i + 1).padStart(2, "0")}</span>
                  </div>
                  <h3 className="lift-1 mt-6 text-[17px] font-semibold tracking-[-0.01em] text-ink">{c.title}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-ink-2">{c.body}</p>
                </Tilt>
              </Reveal>
            ))}
          </div>
        </section>

        {/* Call to action */}
        <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6 lg:pb-28">
          <Reveal>
            <div className="relative overflow-hidden rounded-xl bg-night px-6 py-14 sm:px-12 sm:py-16">
              <div
                aria-hidden="true"
                className="absolute inset-0 opacity-[0.35] [background-image:linear-gradient(rgb(var(--night-line))_1px,transparent_1px),linear-gradient(90deg,rgb(var(--night-line))_1px,transparent_1px)] [background-size:32px_32px] [mask-image:linear-gradient(90deg,transparent,black_60%)]"
              />
              <div className="relative grid gap-8 lg:grid-cols-[1.4fr_1fr] lg:items-end">
                <div>
                  <h2 className="text-3xl font-semibold tracking-[-0.025em] text-night-ink sm:text-[2.5rem] sm:leading-[1.1]">
                    Bring your hospital into the network.
                  </h2>
                  <p className="mt-4 max-w-lg text-[17px] leading-relaxed text-night-muted">
                    Register a node, upload images to your own store, and join the next training round.
                    No data leaves your hospital.
                  </p>
                </div>
                <div className="flex flex-col gap-3 sm:flex-row lg:justify-end">
                  <Link href="/signup" className={buttonClass("inverse", "lg")}>
                    Create hospital account
                  </Link>
                  <Link
                    href="/demo"
                    className={buttonClass(
                      "ghost",
                      "lg",
                      "border border-night-line text-night-ink hover:bg-white/5 hover:text-night-ink",
                    )}
                  >
                    Try the simulation
                  </Link>
                </div>
              </div>
            </div>
          </Reveal>
        </section>
      </main>
      <Footer />
    </>
  );
}
