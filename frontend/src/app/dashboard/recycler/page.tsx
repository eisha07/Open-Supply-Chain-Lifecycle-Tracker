// Recycler / Dismantler Dashboard
"use client";

import { useState, useEffect } from "react";
import { Recycle, Download, AlertTriangle, Package, Loader } from "lucide-react";
import Link from "next/link";
import { listTwins, getRecyclingMatrix, getSecondLifeEstimate } from "@/lib/api";
import type { TwinRead, RecyclingMatrix, SecondLifeEstimate } from "@/lib/types";
import { TwinCard } from "@/components/TwinCard";

export default function RecyclerDashboard() {
  const [twins, setTwins] = useState<TwinRead[]>([]);
  const [selected, setSelected] = useState<TwinRead | null>(null);
  const [matrix, setMatrix] = useState<RecyclingMatrix | null>(null);
  const [secondLife, setSecondLife] = useState<SecondLifeEstimate | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingTwins, setLoadingTwins] = useState(true);

  useEffect(() => {
    setLoadingTwins(true);
    listTwins({ limit: 100 })
      .then(setTwins)
      .catch(() => {})
      .finally(() => setLoadingTwins(false));
  }, []);

  const handleSelect = async (twin: TwinRead) => {
    setSelected(twin);
    setMatrix(null);
    setSecondLife(null);
    setLoading(true);
    const [m, s] = await Promise.all([
      getRecyclingMatrix(twin.id).catch(() => null),
      getSecondLifeEstimate(twin.id).catch(() => null),
    ]);
    setMatrix(m);
    setSecondLife(s);
    setLoading(false);
  };

  const exportMatrix = () => {
    if (!matrix) return;
    const blob = new Blob([JSON.stringify(matrix, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `recycling-matrix-${matrix.twin_id.slice(-12)}.json`;
    a.click();
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Recycle size={18} className="text-teal-400" />
          <span className="font-semibold text-sm">Recycler / Dismantler Dashboard</span>
        </div>
        <Link href="/" className="text-xs text-white/30 hover:text-white/60 transition-colors">← Home</Link>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Asset list */}
        <aside>
          <h2 className="text-xs uppercase tracking-widest text-white/30 mb-4">Assets</h2>
          <div className="space-y-3 max-h-[calc(100vh-180px)] overflow-y-auto pr-1">
            {loadingTwins ? (
              <div className="flex justify-center py-8">
                <Loader size={20} className="animate-spin text-white/20" />
              </div>
            ) : twins.length === 0 ? (
              <p className="text-xs text-white/25 text-center py-8">No twins found.</p>
            ) : (
              twins.map((t) => (
                <TwinCard key={t.id} twin={t} showSoH={false} onClick={handleSelect} />
              ))
            )}
          </div>
        </aside>

        {/* Main content */}
        <main className="lg:col-span-2 space-y-5">
          {selected ? (
            <>
              <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <h1 className="text-lg font-bold">{selected.name}</h1>
                    <p className="text-xs text-white/40">{selected.product_type}</p>
                  </div>
                  {matrix && (
                    <button
                      onClick={exportMatrix}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-teal-500/20 hover:bg-teal-500/30 text-teal-300 rounded-lg transition-colors"
                    >
                      <Download size={12} /> Export JSON
                    </button>
                  )}
                </div>
              </div>

              {/* Second life estimate */}
              {secondLife && (
                <div className={`border rounded-2xl p-5 ${
                  secondLife.suitable_for_automotive ? "border-green-500/20 bg-green-500/5"
                  : secondLife.suitable_for_stationary_storage ? "border-blue-500/20 bg-blue-500/5"
                  : "border-red-500/20 bg-red-500/5"
                }`}>
                  <h2 className="text-sm font-semibold mb-2 flex items-center gap-2">
                    <Package size={14} className="text-white/50" />
                    Second-Life Recommendation
                  </h2>
                  <p className="text-xs font-mono font-bold text-white mb-2">
                    {secondLife.recommendation}
                  </p>
                  <p className="text-xs text-white/50 leading-relaxed">{secondLife.reasoning}</p>
                </div>
              )}

              {/* Recycling matrix */}
              {loading && <p className="text-xs text-white/30 text-center py-8">Loading matrix…</p>}
              {matrix && (
                <>
                  {/* Hazards */}
                  {matrix.hazardous_materials.length > 0 && (
                    <div className="bg-red-950/20 border border-red-500/15 rounded-2xl p-5">
                      <h2 className="text-sm font-semibold mb-4 flex items-center gap-2 text-red-300">
                        <AlertTriangle size={14} /> Hazardous Materials
                      </h2>
                      <div className="space-y-3">
                        {matrix.hazardous_materials.map((h) => (
                          <div key={h.material} className="bg-white/[0.03] rounded-xl p-3 text-xs space-y-1">
                            <p className="font-semibold text-red-300 capitalize">{h.material}</p>
                            <p className="text-white/40">{h.hazard_class}</p>
                            <p className="text-white/50"><span className="text-white/30">PPE: </span>{h.ppe_required}</p>
                            <p className="text-white/50"><span className="text-white/30">Disposal: </span>{h.disposal}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Target metals */}
                  <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                    <h2 className="text-sm font-semibold mb-4">
                      Target Metals
                      <span className="ml-2 text-xs text-green-400 font-mono">
                        Est. ~${matrix.estimated_recovery_value_usd.toFixed(2)} USD
                      </span>
                    </h2>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-white/30 border-b border-white/5">
                            <th className="text-left pb-2">Metal</th>
                            <th className="text-right pb-2">Gross (kg)</th>
                            <th className="text-right pb-2">Recoverable (kg)</th>
                            <th className="text-right pb-2">Purity</th>
                            <th className="text-right pb-2">Est. Value</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.04]">
                          {matrix.target_metals.map((m) => (
                            <tr key={m.metal}>
                              <td className="py-2 font-medium capitalize text-white/80">{m.metal}</td>
                              <td className="text-right text-white/50">{m.gross_weight_kg}</td>
                              <td className="text-right text-white/50">{m.recoverable_kg}</td>
                              <td className="text-right text-green-400">{m.recovery_purity_pct}%</td>
                              <td className="text-right text-white/70">${m.estimated_value_usd}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Disassembly sequence */}
                  <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                    <h2 className="text-sm font-semibold mb-4">Disassembly Sequence</h2>
                    <ol className="space-y-2">
                      {matrix.disassembly_sequence.map((step) => (
                        <li key={step.step} className="flex gap-3 text-xs">
                          <span className="w-5 h-5 rounded-full bg-teal-500/15 text-teal-400 flex items-center justify-center flex-shrink-0 font-mono font-bold">
                            {step.step}
                          </span>
                          <span className={`text-white/60 leading-relaxed ${step.step === 0 ? "text-red-300 font-semibold" : ""}`}>
                            {step.action}
                          </span>
                        </li>
                      ))}
                    </ol>
                  </div>

                  {/* Regulatory refs */}
                  <div className="text-xs text-white/25 flex flex-wrap gap-2">
                    {matrix.regulatory_references.map((r) => (
                      <span key={r} className="bg-white/5 px-2 py-0.5 rounded">{r}</span>
                    ))}
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-white/20 gap-3">
              <Recycle size={32} />
              <p className="text-sm">Select an asset to view its recycling matrix</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
