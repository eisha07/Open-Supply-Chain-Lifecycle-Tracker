// OEM Manufacturer Dashboard — assembly & BOM management
"use client";

import { useState, useEffect } from "react";
import { Cpu, Plus, GitBranch, Shield } from "lucide-react";
import Link from "next/link";
import { listTwins, createTwin, getTwinChildren, generateZkpFlags } from "@/lib/api";
import type { TwinRead } from "@/lib/types";
import { TwinCard } from "@/components/TwinCard";
import { EventTimeline } from "@/components/EventTimeline";

export default function OemDashboard() {
  const [twins, setTwins] = useState<TwinRead[]>([]);
  const [selected, setSelected] = useState<TwinRead | null>(null);
  const [children, setChildren] = useState<TwinRead[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [actorDid, setActorDid] = useState("");
  const [zkpDid, setZkpDid] = useState("");
  const [zkpResult, setZkpResult] = useState<Record<string, unknown> | null>(null);
  const [form, setForm] = useState({
    name: "", product_type: "BATTERY_PACK",
    parent_twin_id: "", initial_capacity_kwh: "",
  });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { listTwins({ limit: 100 }).then(setTwins).catch(() => {}); }, []);

  const handleSelect = async (twin: TwinRead) => {
    setSelected(twin);
    setZkpResult(null);
    const kids = await getTwinChildren(twin.id).catch(() => []);
    setChildren(kids);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actorDid) { setError("Actor DID required"); return; }
    setCreating(true); setError(null);
    try {
      const twin = await createTwin(actorDid, {
        name: form.name,
        product_type: form.product_type,
        parent_twin_id: form.parent_twin_id || undefined,
        initial_capacity_kwh: form.initial_capacity_kwh ? Number(form.initial_capacity_kwh) : undefined,
      });
      setTwins((prev) => [twin, ...prev]);
      setShowForm(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally { setCreating(false); }
  };

  const handleGenerateZkp = async () => {
    if (!selected || !zkpDid) return;
    try {
      const result = await generateZkpFlags(selected.id, zkpDid, {
        is_conflict_free: true,
        recycled_cobalt_pct_gte: 30,
        eu_battery_regulation_compliant: true,
      });
      setZkpResult(result.zkp_flags);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "ZKP failed");
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Cpu size={18} className="text-blue-400" />
          <span className="font-semibold text-sm">OEM Manufacturer Dashboard</span>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setShowForm(true)} className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 rounded-lg transition-colors">
            <Plus size={12} /> Assemble Twin
          </button>
          <Link href="/" className="text-xs text-white/30 hover:text-white/60 transition-colors">← Home</Link>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <aside>
          <h2 className="text-xs uppercase tracking-widest text-white/30 mb-4">Twins</h2>
          {showForm && (
            <form onSubmit={handleCreate} className="bg-white/[0.04] border border-white/10 rounded-2xl p-4 mb-4 space-y-3">
              <h3 className="text-xs font-semibold text-white/70">New Twin</h3>
              {[
                ["Actor DID", actorDid, setActorDid, "did:key:z6Mk…", true],
                ["Name", form.name, (v: string) => setForm((f) => ({ ...f, name: v })), "Battery Pack BP-001", true],
                ["Product Type", form.product_type, (v: string) => setForm((f) => ({ ...f, product_type: v })), "BATTERY_PACK"],
                ["Parent Twin DID", form.parent_twin_id, (v: string) => setForm((f) => ({ ...f, parent_twin_id: v })), "did:key:… (optional)"],
                ["Capacity kWh", form.initial_capacity_kwh, (v: string) => setForm((f) => ({ ...f, initial_capacity_kwh: v })), "75.0"],
              ].map(([lbl, val, fn, ph, req]) => (
                <div key={String(lbl)}>
                  <label className="block text-[10px] text-white/30 mb-0.5">{String(lbl)}</label>
                  <input value={String(val)} onChange={(e) => (fn as (v: string) => void)(e.target.value)}
                    placeholder={String(ph)} required={Boolean(req)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-white/15 focus:outline-none focus:border-blue-400/30" />
                </div>
              ))}
              {error && <p className="text-[10px] text-red-400">{error}</p>}
              <div className="flex gap-2">
                <button type="submit" disabled={creating} className="text-[11px] px-3 py-1.5 bg-blue-500/30 text-blue-300 rounded-lg disabled:opacity-50">
                  {creating ? "…" : "Create"}
                </button>
                <button type="button" onClick={() => setShowForm(false)} className="text-[11px] px-3 py-1.5 bg-white/5 rounded-lg">Cancel</button>
              </div>
            </form>
          )}
          <div className="space-y-2 max-h-[calc(100vh-220px)] overflow-y-auto">
            {twins.map((t) => (
              <TwinCard key={t.id} twin={t} showSoH={false} onClick={handleSelect} />
            ))}
          </div>
        </aside>

        <main className="lg:col-span-2 space-y-5">
          {selected ? (
            <>
              <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                <h1 className="text-lg font-bold">{selected.name}</h1>
                <p className="text-xs text-white/40 mb-2">{selected.product_type} · v{selected.version_id}</p>
                <p className="text-xs font-mono text-white/20 break-all">{selected.id}</p>
              </div>

              {/* BOM children */}
              {children.length > 0 && (
                <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                  <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                    <GitBranch size={14} className="text-blue-400" /> Bill of Materials ({children.length})
                  </h2>
                  <div className="space-y-2">
                    {children.map((c) => (
                      <div key={c.id} className="flex items-center justify-between bg-white/[0.02] rounded-lg px-3 py-2 text-xs">
                        <span className="text-white/70">{c.name}</span>
                        <span className="text-white/30">{c.product_type}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ZKP generation */}
              <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Shield size={14} className="text-purple-400" /> Generate ZKP Disclosure Flags
                </h2>
                <div className="flex gap-2 mb-3">
                  <input value={zkpDid} onChange={(e) => setZkpDid(e.target.value)}
                    placeholder="Your OEM Actor DID"
                    className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white placeholder-white/20 focus:outline-none" />
                  <button onClick={handleGenerateZkp} className="text-xs px-3 py-1.5 bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 rounded-lg transition-colors">
                    Generate
                  </button>
                </div>
                {zkpResult && (
                  <pre className="text-[10px] text-white/40 bg-black/30 rounded-lg p-3 overflow-x-auto max-h-48">
                    {JSON.stringify(zkpResult, null, 2)}
                  </pre>
                )}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-white/20 gap-3">
              <Cpu size={32} />
              <p className="text-sm">Select a twin to inspect its BOM and generate ZKP flags</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
