// OEM Manufacturer Dashboard — assembly, BOM, ZKP, full twin creation form
"use client";

import { useState, useEffect } from "react";
import { Cpu, Plus, GitBranch, Shield, Loader, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { listTwins, createTwin, getTwinChildren, generateZkpFlags } from "@/lib/api";
import type { TwinRead } from "@/lib/types";
import { TwinCard } from "@/components/TwinCard";

type KVEntry = { key: string; value: string };

function kvToRecord(entries: KVEntry[]): Record<string, number> | undefined {
  const valid = entries.filter((e) => e.key.trim() && e.value.trim());
  if (valid.length === 0) return undefined;
  return Object.fromEntries(valid.map((e) => [e.key.trim(), parseFloat(e.value)]));
}

export default function OemDashboard() {
  const [twins, setTwins] = useState<TwinRead[]>([]);
  const [loadingTwins, setLoadingTwins] = useState(true);
  const [selected, setSelected] = useState<TwinRead | null>(null);
  const [children, setChildren] = useState<TwinRead[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [actorDid, setActorDid] = useState("");
  const [zkpDid, setZkpDid] = useState("");
  const [zkpResult, setZkpResult] = useState<Record<string, unknown> | null>(null);
  const [form, setForm] = useState({
    name: "",
    product_type: "BATTERY_PACK",
    parent_twin_id: "",
    serial_number: "",
    initial_capacity_kwh: "",
    initial_safety_rating: "",
  });
  const [materialWeights, setMaterialWeights] = useState<KVEntry[]>([
    { key: "lithium", value: "" },
    { key: "cobalt", value: "" },
  ]);
  const [baselineChemistry, setBaselineChemistry] = useState<KVEntry[]>([
    { key: "NMC_811", value: "" },
  ]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zkpLoading, setZkpLoading] = useState(false);

  useEffect(() => {
    setLoadingTwins(true);
    listTwins({ limit: 100 })
      .then(setTwins)
      .catch(() => {})
      .finally(() => setLoadingTwins(false));
  }, []);

  const handleSelect = async (twin: TwinRead) => {
    setSelected(twin);
    setZkpResult(null);
    setError(null);
    const kids = await getTwinChildren(twin.id).catch(() => []);
    setChildren(kids);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actorDid.trim()) { setError("Actor DID required"); return; }
    setCreating(true);
    setError(null);
    try {
      const twin = await createTwin(actorDid.trim(), {
        name: form.name,
        product_type: form.product_type,
        parent_twin_id: form.parent_twin_id || undefined,
        serial_number: form.serial_number || undefined,
        initial_capacity_kwh: form.initial_capacity_kwh ? Number(form.initial_capacity_kwh) : undefined,
        initial_safety_rating: form.initial_safety_rating || undefined,
        material_weights_kg: kvToRecord(materialWeights),
        baseline_chemistry: kvToRecord(baselineChemistry),
      });
      setTwins((prev) => [twin, ...prev]);
      setShowForm(false);
      setShowAdvanced(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setCreating(false);
    }
  };

  const handleGenerateZkp = async () => {
    if (!selected || !zkpDid) return;
    setZkpLoading(true);
    setError(null);
    try {
      const result = await generateZkpFlags(selected.id, zkpDid, {
        is_conflict_free: true,
        recycled_cobalt_pct_gte: 30,
        eu_battery_regulation_compliant: true,
      });
      setZkpResult(result.zkp_flags);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "ZKP failed");
    } finally {
      setZkpLoading(false);
    }
  };

  const addKV = (setter: React.Dispatch<React.SetStateAction<KVEntry[]>>) => {
    setter((prev) => [...prev, { key: "", value: "" }]);
  };
  const updateKV = (
    setter: React.Dispatch<React.SetStateAction<KVEntry[]>>,
    idx: number, field: keyof KVEntry, val: string
  ) => { setter((prev) => prev.map((e, i) => (i === idx ? { ...e, [field]: val } : e))); };
  const removeKV = (setter: React.Dispatch<React.SetStateAction<KVEntry[]>>, idx: number) => {
    setter((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Cpu size={18} className="text-blue-400" />
          <span className="font-semibold text-sm">OEM Manufacturer Dashboard</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { setShowForm(true); setError(null); }}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 rounded-lg transition-colors"
          >
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
              <h3 className="text-xs font-semibold text-white/70">New Assembly Twin</h3>

              {error && (
                <div className="flex items-center gap-1.5 text-[10px] text-red-400 bg-red-950/30 border border-red-500/20 rounded-lg px-2 py-1.5">
                  <AlertTriangle size={10} /> {error}
                </div>
              )}

              {[
                { lbl: "Actor DID *", val: actorDid, fn: setActorDid, ph: "did:key:z6Mk…", req: true },
                { lbl: "Name *", val: form.name, fn: (v: string) => setForm((f) => ({ ...f, name: v })), ph: "Battery Pack BP-001", req: true },
                { lbl: "Product Type", val: form.product_type, fn: (v: string) => setForm((f) => ({ ...f, product_type: v })), ph: "BATTERY_PACK" },
                { lbl: "Parent Twin DID", val: form.parent_twin_id, fn: (v: string) => setForm((f) => ({ ...f, parent_twin_id: v })), ph: "did:key:… (optional)" },
                { lbl: "Serial Number", val: form.serial_number, fn: (v: string) => setForm((f) => ({ ...f, serial_number: v })), ph: "SN-001" },
                { lbl: "Capacity kWh", val: form.initial_capacity_kwh, fn: (v: string) => setForm((f) => ({ ...f, initial_capacity_kwh: v })), ph: "75.0" },
                { lbl: "Safety Rating", val: form.initial_safety_rating, fn: (v: string) => setForm((f) => ({ ...f, initial_safety_rating: v })), ph: "IEC62619" },
              ].map(({ lbl, val, fn, ph, req }) => (
                <div key={String(lbl)}>
                  <label className="block text-[10px] text-white/30 mb-0.5">{lbl}</label>
                  <input
                    value={String(val)}
                    onChange={(e) => (fn as (v: string) => void)(e.target.value)}
                    placeholder={String(ph)}
                    required={Boolean(req)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-white/15 focus:outline-none focus:border-blue-400/30"
                  />
                </div>
              ))}

              {/* Advanced material fields */}
              <button
                type="button"
                onClick={() => setShowAdvanced((v) => !v)}
                className="flex items-center gap-1.5 text-[10px] text-white/30 hover:text-white/60 transition-colors"
              >
                {showAdvanced ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                Material composition
              </button>

              {showAdvanced && (
                <div className="space-y-3 border-t border-white/5 pt-3">
                  {[
                    { label: "Material Weights (kg)", entries: materialWeights, setter: setMaterialWeights, keyPh: "lithium", valPh: "2.1" },
                    { label: "Chemistry (fraction)", entries: baselineChemistry, setter: setBaselineChemistry, keyPh: "NMC_811", valPh: "0.85" },
                  ].map(({ label, entries, setter, keyPh, valPh }) => (
                    <div key={label}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-white/25">{label}</span>
                        <button type="button" onClick={() => addKV(setter)} className="text-[9px] text-blue-400">+ Add</button>
                      </div>
                      {entries.map((entry, i) => (
                        <div key={i} className="flex gap-1 mb-1">
                          <input value={entry.key} onChange={(e) => updateKV(setter, i, "key", e.target.value)}
                            placeholder={keyPh}
                            className="flex-1 bg-white/5 border border-white/10 rounded px-2 py-1 text-[10px] text-white placeholder-white/15 focus:outline-none" />
                          <input value={entry.value} onChange={(e) => updateKV(setter, i, "value", e.target.value)}
                            placeholder={valPh} type="number"
                            className="w-16 bg-white/5 border border-white/10 rounded px-2 py-1 text-[10px] text-white placeholder-white/15 focus:outline-none" />
                          <button type="button" onClick={() => removeKV(setter, i)}
                            className="text-[10px] text-red-400/50 hover:text-red-400">×</button>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}

              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={creating}
                  className="flex items-center gap-1.5 text-[11px] px-3 py-1.5 bg-blue-500/30 text-blue-300 rounded-lg disabled:opacity-50 transition-colors"
                >
                  {creating ? <Loader size={10} className="animate-spin" /> : null}
                  {creating ? "…" : "Create"}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowForm(false); setShowAdvanced(false); }}
                  className="text-[11px] px-3 py-1.5 bg-white/5 rounded-lg transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}

          {loadingTwins ? (
            <div className="flex justify-center py-8">
              <Loader size={20} className="animate-spin text-white/20" />
            </div>
          ) : (
            <div className="space-y-2 max-h-[calc(100vh-220px)] overflow-y-auto">
              {twins.map((t) => (
                <TwinCard key={t.id} twin={t} showSoH={false} onClick={handleSelect} />
              ))}
            </div>
          )}
        </aside>

        <main className="lg:col-span-2 space-y-5">
          {selected ? (
            <>
              <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                <h1 className="text-lg font-bold">{selected.name}</h1>
                <p className="text-xs text-white/40 mb-2">{selected.product_type} · v{selected.version_id}</p>
                <p className="text-xs font-mono text-white/20 break-all">{selected.id}</p>
                {selected.material_weights_kg && (
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {Object.entries(selected.material_weights_kg).map(([k, v]) => (
                      <div key={k} className="bg-white/[0.02] rounded-lg px-2.5 py-1.5 text-xs">
                        <span className="text-white/30">{k}: </span>
                        <span className="text-white/70">{v} kg</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

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

              <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Shield size={14} className="text-purple-400" /> Generate ZKP Disclosure Flags
                </h2>
                <div className="flex gap-2 mb-3">
                  <input
                    value={zkpDid}
                    onChange={(e) => setZkpDid(e.target.value)}
                    placeholder="Your OEM Actor DID"
                    className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white placeholder-white/20 focus:outline-none"
                  />
                  <button
                    onClick={handleGenerateZkp}
                    disabled={zkpLoading}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {zkpLoading ? <Loader size={11} className="animate-spin" /> : null}
                    {zkpLoading ? "…" : "Generate"}
                  </button>
                </div>
                {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
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
