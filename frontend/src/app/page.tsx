"use client";

import ChromaGrid from "@/components/ChromaGrid/ChromaGrid";
import { ShieldCheck, Zap, Cpu, Recycle, Globe, BookOpen } from "lucide-react";

// ChromaGrid items — one per supply-chain role
const ROLE_ITEMS = [
  {
    image: "https://i.pravatar.cc/300?img=32",
    title: "Raw Material Supplier",
    subtitle: "Instantiate material batches & assign origin DIDs",
    handle: "/dashboard/supplier",
    borderColor: "#22c55e",
    gradient: "linear-gradient(145deg, #14532d, #000)",
    url: "/dashboard/supplier",
  },
  {
    image: "https://i.pravatar.cc/300?img=12",
    title: "OEM Manufacturer",
    subtitle: "Assemble hierarchical BOM Digital Twins",
    handle: "/dashboard/oem",
    borderColor: "#3b82f6",
    gradient: "linear-gradient(165deg, #1e3a8a, #000)",
    url: "/dashboard/oem",
  },
  {
    image: "https://i.pravatar.cc/300?img=57",
    title: "Field Technician",
    subtitle: "Log repairs, telemetry & offline-queue sync",
    handle: "/dashboard/technician",
    borderColor: "#f59e0b",
    gradient: "linear-gradient(195deg, #78350f, #000)",
    url: "/dashboard/technician",
  },
  {
    image: "https://i.pravatar.cc/300?img=47",
    title: "Recycler / Dismantler",
    subtitle: "Query material profiles & dismantling matrix",
    handle: "/dashboard/recycler",
    borderColor: "#14b8a6",
    gradient: "linear-gradient(210deg, #134e4a, #000)",
    url: "/dashboard/recycler",
  },
  {
    image: "https://i.pravatar.cc/300?img=20",
    title: "Public / QR Scan",
    subtitle: "View provenance passport & safety data",
    handle: "/passport/[twin_id]",
    borderColor: "#8b5cf6",
    gradient: "linear-gradient(225deg, #3b0764, #000)",
    url: "#scan",
  },
  {
    image: "https://i.pravatar.cc/300?img=40",
    title: "API Explorer",
    subtitle: "OpenAPI / Swagger docs & integration guide",
    handle: "/docs (backend)",
    borderColor: "#f472b6",
    gradient: "linear-gradient(135deg, #500724, #000)",
    url: "http://localhost:8000/docs",
  },
];

const STATS = [
  { label: "Ed25519 Signatures", value: "Every event" },
  { label: "Append-Only Ledger", value: "Immutable chain" },
  { label: "EU DPP Aligned", value: "ESPR 2024" },
  { label: "Zero-Knowledge Proofs", value: "Privacy-first" },
];

export default function HomePage() {
  return (
    <main className="flex flex-col min-h-screen bg-[#0a0a0f] text-white">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck className="text-green-400" size={22} />
          <span className="font-bold tracking-tight text-sm uppercase text-white/80">
            OSLT — Open Supply Lifecycle Tracker
          </span>
        </div>
        <nav className="hidden md:flex items-center gap-6 text-sm text-white/50">
          <a href="/dashboard/supplier" className="hover:text-white transition-colors">Supplier</a>
          <a href="/dashboard/oem" className="hover:text-white transition-colors">OEM</a>
          <a href="/dashboard/technician" className="hover:text-white transition-colors">Technician</a>
          <a href="/dashboard/recycler" className="hover:text-white transition-colors">Recycler</a>
          <a href="/actors" className="hover:text-white transition-colors">Actors</a>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 rounded border border-white/15 hover:bg-white/5 transition-colors"
          >
            API Docs
          </a>
        </nav>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <section className="px-6 pt-16 pb-10 max-w-4xl mx-auto w-full text-center">
        <div className="inline-flex items-center gap-2 text-xs text-green-400 bg-green-400/10 border border-green-400/20 rounded-full px-3 py-1 mb-6">
          <Zap size={12} />
          EU DPP / ESPR Compliant · Ed25519 Cryptography · Append-Only Ledger
        </div>
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-5 leading-tight">
          Digital Product Passports<br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-blue-500">
            for Physical Assets
          </span>
        </h1>
        <p className="text-white/50 text-lg max-w-2xl mx-auto leading-relaxed">
          Cryptographically verifiable supply-chain provenance for batteries, EVs, and
          raw materials — from extraction through manufacturing, repair, and recycling.
        </p>
      </section>

      {/* ── Stats Row ───────────────────────────────────────────────────────── */}
      <section className="max-w-4xl mx-auto w-full px-6 mb-10">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {STATS.map((s) => (
            <div
              key={s.label}
              className="bg-white/[0.03] border border-white/5 rounded-xl p-4"
            >
              <p className="text-xs text-white/40 mb-1">{s.label}</p>
              <p className="text-sm font-semibold text-white">{s.value}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── ChromaGrid Role Selector ─────────────────────────────────────────── */}
      <section className="flex-1 px-4 pb-10 max-w-5xl mx-auto w-full">
        <p className="text-xs text-white/30 uppercase tracking-widest mb-4 text-center">
          Select your role to enter the dashboard
        </p>
        <div style={{ height: "480px", position: "relative" }}>
          <ChromaGrid
            items={ROLE_ITEMS}
            radius={320}
            damping={0.42}
            fadeOut={0.55}
            ease="power3.out"
            columns={3}
            rows={2}
          />
        </div>
      </section>

      {/* ── Features Strip ──────────────────────────────────────────────────── */}
      <section className="border-t border-white/5 px-6 py-10">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { icon: <Cpu size={18} />, label: "Digital Twins", desc: "Hierarchical BOM from cell → pack → EV" },
            { icon: <ShieldCheck size={18} />, label: "ZKP Privacy", desc: "Prove claims without revealing supplier secrets" },
            { icon: <Recycle size={18} />, label: "Recycling Matrix", desc: "Auto-generated dismantling guide per asset" },
            { icon: <Globe size={18} />, label: "Public Passport", desc: "QR-scannable provenance for end consumers" },
          ].map((f) => (
            <div key={f.label} className="flex flex-col gap-2">
              <div className="text-green-400">{f.icon}</div>
              <p className="text-sm font-semibold text-white">{f.label}</p>
              <p className="text-xs text-white/40 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── QR Scan Section ─────────────────────────────────────────────────── */}
      <section
        id="scan"
        className="border-t border-white/5 px-6 py-10 max-w-2xl mx-auto w-full text-center"
      >
        <BookOpen className="mx-auto mb-3 text-purple-400" size={28} />
        <h2 className="text-xl font-bold mb-2">Scan a Digital Product Passport</h2>
        <p className="text-white/40 text-sm mb-5">
          Enter a twin DID below to view its public provenance timeline.
        </p>
        <ScanForm />
      </section>
    </main>
  );
}

function ScanForm() {
  "use client";
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const did = (form.elements.namedItem("did") as HTMLInputElement).value.trim();
    if (did) window.location.href = `/passport/${encodeURIComponent(did)}`;
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 max-w-md mx-auto">
      <input
        name="did"
        type="text"
        placeholder="did:key:z6Mk…"
        className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder-white/25 focus:outline-none focus:border-purple-400/50"
      />
      <button
        type="submit"
        className="px-5 py-2.5 bg-purple-500 hover:bg-purple-400 rounded-lg text-sm font-medium transition-colors"
      >
        View
      </button>
    </form>
  );
}
