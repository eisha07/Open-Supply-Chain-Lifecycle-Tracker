// Supplier Dashboard — create material batch twins with full field support
"use client";

import { useState, useEffect } from "react";
import { Pickaxe, Plus, Loader, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { listTwins, createTwin } from "@/lib/api";
import type { TwinRead } from "@/lib/types";
import { TwinCard } from "@/components/TwinCard";

type KVEntry = { key: string; value: string };

function kvToRecord(entries: KVEntry[]): Record<string, number> | undefined {
  const valid = entries.filter((e) => e.key.trim() && e.value.trim());
  if (valid.length === 0) return undefined;
  return Object.fromEntries(valid.map((e) => [e.key.trim(), parseFloat(e.value)]));
}

export default function SupplierDashboard() {
  const [twins, setTwins] = useState<TwinRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [actorDid, setActorDid] = useState("");
  const [form, setForm] = useState({
    name: "",
    product_type: "RAW_MATERIAL_BATCH",
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

  useEffect(() => {
    setLoading(true);
    listTwins({ limit: 50 })
      .then(setTwins)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actorDid.trim()) { setError("Actor DID is required"); return; }
    setCreating(true);
    setError(null);
    try {
      const twin = await createTwin(actorDid.trim(), {
        name: form.name,
        product_type: form.product_type,
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
      setError(err instanceof Error ? err.message : "Failed to create twin");
    } finally {
      setCreating(false);
    }
  };

  const addKV = (setter: React.Dispatch<React.SetStateAction<KVEntry[]>>) => {
    setter((prev) => [...prev, { key: "", value: "" }]);
  };

  const updateKV = (
    setter: React.Dispatch<React.SetStateAction<KVEntry[]>>,
    idx: number,
    field: keyof KVEntry,
    val: string
  ) => {
    setter((prev) => prev.map((e, i) => (i === idx ? { ...e, [field]: val } : e)));
  };

  const removeKV = (setter: React.Dispatch<React.SetStateAction<KVEntry[]>>, idx: number) => {
    setter((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Pickaxe size={18} className="text-green-400" />
          <span className="font-semibold text-sm">Raw Material Supplier Dashboard</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { setShowForm(true); setError(null); }}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30 text-green-300 rounded-lg transition-colors"
          >
            <Plus size={12} /> New Material Batch
          </button>
          <Link href="/" className="text-xs text-white/30 hover:text-white/60 transition-colors">← Home</Link>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8">
        {showForm && (
          <form onSubmit={handleCreate} className="bg-white/[0.04] border border-white/10 rounded-2xl p-6 mb-8 space-y-4">
            <h2 className="text-sm font-semibold mb-2">Instantiate Material Batch Twin</h2>

            {/* Core fields */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field
                label="Your Actor DID *"
                value={actorDid}
                onChange={setActorDid}
                placeholder="did:key:z6Mk…"
                required
              />
              <Field
                label="Batch Name *"
                value={form.name}
                onChange={(v) => setForm((f) => ({ ...f, name: v }))}
                placeholder="Lithium Batch LB-2024-001"
                required
              />
              <Field
                label="Product Type"
                value={form.product_type}
                onChange={(v) => setForm((f) => ({ ...f, product_type: v }))}
                placeholder="RAW_MATERIAL_BATCH"
              />
              <Field
                label="Serial Number"
                value={form.serial_number}
                onChange={(v) => setForm((f) => ({ ...f, serial_number: v }))}
                placeholder="SN-2024-LB-001"
              />
              <Field
                label="Initial Capacity (kWh)"
                value={form.initial_capacity_kwh}
                onChange={(v) => setForm((f) => ({ ...f, initial_capacity_kwh: v }))}
                placeholder="100.0"
                type="number"
              />
              <Field
                label="Safety Rating"
                value={form.initial_safety_rating}
                onChange={(v) => setForm((f) => ({ ...f, initial_safety_rating: v }))}
                placeholder="UN38.3 / IEC62619"
              />
            </div>

            {/* Advanced: material weights & chemistry */}
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="flex items-center gap-2 text-xs text-white/40 hover:text-white/70 transition-colors"
            >
              {showAdvanced ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              {showAdvanced ? "Hide" : "Show"} Material Composition
            </button>

            {showAdvanced && (
              <div className="space-y-4 pt-2 border-t border-white/5">
                {/* Material weights */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs text-white/40">Material Weights (kg)</label>
                    <button
                      type="button"
                      onClick={() => addKV(setMaterialWeights)}
                      className="text-[10px] text-green-400 hover:text-green-300"
                    >
                      + Add material
                    </button>
                  </div>
                  <div className="space-y-2">
                    {materialWeights.map((entry, i) => (
                      <div key={i} className="flex gap-2">
                        <input
                          value={entry.key}
                          onChange={(e) => updateKV(setMaterialWeights, i, "key", e.target.value)}
                          placeholder="lithium"
                          className="flex-1 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-white/20 focus:outline-none"
                        />
                        <input
                          type="number"
                          value={entry.value}
                          onChange={(e) => updateKV(setMaterialWeights, i, "value", e.target.value)}
                          placeholder="2.1"
                          className="w-24 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-white/20 focus:outline-none"
                        />
                        <button
                          type="button"
                          onClick={() => removeKV(setMaterialWeights, i)}
                          className="text-xs text-red-400/50 hover:text-red-400 px-1"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Baseline chemistry */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs text-white/40">Baseline Chemistry (fraction, 0–1)</label>
                    <button
                      type="button"
                      onClick={() => addKV(setBaselineChemistry)}
                      className="text-[10px] text-green-400 hover:text-green-300"
                    >
                      + Add component
                    </button>
                  </div>
                  <div className="space-y-2">
                    {baselineChemistry.map((entry, i) => (
                      <div key={i} className="flex gap-2">
                        <input
                          value={entry.key}
                          onChange={(e) => updateKV(setBaselineChemistry, i, "key", e.target.value)}
                          placeholder="NMC_811"
                          className="flex-1 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-white/20 focus:outline-none"
                        />
                        <input
                          type="number"
                          value={entry.value}
                          onChange={(e) => updateKV(setBaselineChemistry, i, "value", e.target.value)}
                          placeholder="0.85"
                          step="0.01"
                          min="0"
                          max="1"
                          className="w-24 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-white/20 focus:outline-none"
                        />
                        <button
                          type="button"
                          onClick={() => removeKV(setBaselineChemistry, i)}
                          className="text-xs text-red-400/50 hover:text-red-400 px-1"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="flex items-center gap-2 text-xs text-red-400 bg-red-950/30 border border-red-500/20 rounded-lg px-3 py-2">
                <AlertTriangle size={12} /> {error}
              </div>
            )}

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={creating}
                className="flex items-center gap-2 text-xs px-4 py-2 bg-green-500 hover:bg-green-400 text-black font-semibold rounded-lg disabled:opacity-50 transition-colors"
              >
                {creating ? <Loader size={12} className="animate-spin" /> : null}
                {creating ? "Creating…" : "Create Twin"}
              </button>
              <button
                type="button"
                onClick={() => { setShowForm(false); setShowAdvanced(false); }}
                className="text-xs px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        <h2 className="text-xs uppercase tracking-widest text-white/30 mb-5">Your Material Batch Twins</h2>

        {loading ? (
          <div className="flex justify-center py-16">
            <Loader size={28} className="animate-spin text-white/20" />
          </div>
        ) : twins.length === 0 ? (
          <div className="text-center py-16 text-white/20">
            <Pickaxe size={36} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">No twins yet — create your first material batch above.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {twins.map((t) => <TwinCard key={t.id} twin={t} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function Field({
  label, value, onChange, placeholder, required, type = "text",
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; required?: boolean; type?: string;
}) {
  return (
    <div>
      <label className="block text-xs text-white/40 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-green-400/40"
      />
    </div>
  );
}
