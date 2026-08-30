// Supplier Dashboard — create material batch twins
"use client";

import { useState, useEffect } from "react";
import { Pickaxe, Plus } from "lucide-react";
import Link from "next/link";
import { listTwins, createTwin } from "@/lib/api";
import type { TwinRead } from "@/lib/types";
import { TwinCard } from "@/components/TwinCard";

export default function SupplierDashboard() {
  const [twins, setTwins] = useState<TwinRead[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [actorDid, setActorDid] = useState("");
  const [form, setForm] = useState({ name: "", product_type: "RAW_MATERIAL_BATCH", initial_capacity_kwh: "" });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { listTwins({ limit: 50 }).then(setTwins).catch(() => {}); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actorDid) { setError("Actor DID required"); return; }
    setCreating(true); setError(null);
    try {
      const twin = await createTwin(actorDid, {
        name: form.name,
        product_type: form.product_type,
        initial_capacity_kwh: form.initial_capacity_kwh ? Number(form.initial_capacity_kwh) : undefined,
      });
      setTwins((prev) => [twin, ...prev]);
      setShowForm(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create twin");
    } finally { setCreating(false); }
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
            onClick={() => setShowForm(true)}
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field label="Your Actor DID" value={actorDid} onChange={setActorDid} placeholder="did:key:z6Mk…" required />
              <Field label="Batch Name" value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} placeholder="Lithium Batch LB-2024-001" required />
              <Field label="Product Type" value={form.product_type} onChange={(v) => setForm((f) => ({ ...f, product_type: v }))} placeholder="RAW_MATERIAL_BATCH" />
              <Field label="Initial Capacity (kWh)" value={form.initial_capacity_kwh} onChange={(v) => setForm((f) => ({ ...f, initial_capacity_kwh: v }))} placeholder="100.0" type="number" />
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <div className="flex gap-2">
              <button type="submit" disabled={creating} className="text-xs px-4 py-2 bg-green-500 hover:bg-green-400 text-black font-semibold rounded-lg disabled:opacity-50 transition-colors">
                {creating ? "Creating…" : "Create Twin"}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="text-xs px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
                Cancel
              </button>
            </div>
          </form>
        )}

        <h2 className="text-xs uppercase tracking-widest text-white/30 mb-5">Your Material Batch Twins</h2>
        {twins.length === 0 ? (
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

function Field({ label, value, onChange, placeholder, required, type = "text" }: {
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
