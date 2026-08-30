// TwinCard — compact card for displaying a Digital Twin in a list/grid
"use client";

import type { TwinRead } from "@/lib/types";
import { ShieldCheck, AlertTriangle, Info, Zap } from "lucide-react";
import { SoHGauge } from "./SoHGauge";
import Link from "next/link";

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  ACTIVE:                          { label: "Active",            color: "#22c55e", icon: <Zap size={11} /> },
  PROVENANCE_GAP_DETECTED:         { label: "Prov. Gap",         color: "#f59e0b", icon: <Info size={11} /> },
  TAMPERED_SAFETY_RISK:            { label: "Tamper Risk",       color: "#ef4444", icon: <AlertTriangle size={11} /> },
  UNSUITABLE_FOR_AUTOMOTIVE:       { label: "Not Automotive",    color: "#f97316", icon: <AlertTriangle size={11} /> },
  RECOMMENDED_FOR_STATIONARY_STORAGE:{ label: "Stationary",     color: "#06b6d4", icon: <ShieldCheck size={11} /> },
  DECOMMISSIONED:                  { label: "Decommissioned",    color: "#6b7280", icon: <Info size={11} /> },
  SCRAPPED:                        { label: "Scrapped",          color: "#374151", icon: <Info size={11} /> },
};

interface TwinCardProps {
  twin: TwinRead;
  showSoH?: boolean;
  onClick?: (twin: TwinRead) => void;
}

export function TwinCard({ twin, showSoH = true, onClick }: TwinCardProps) {
  const cfg = STATUS_CONFIG[twin.status] ?? STATUS_CONFIG.ACTIVE;

  return (
    <div
      className="group relative bg-white/[0.03] hover:bg-white/[0.055] border border-white/5 hover:border-white/10 rounded-2xl p-4 transition-all cursor-pointer"
      onClick={() => onClick?.(twin)}
    >
      {/* Status badge */}
      <span
        className="absolute top-3 right-3 text-[10px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1"
        style={{ background: cfg.color + "18", color: cfg.color }}
      >
        {cfg.icon}
        {cfg.label}
      </span>

      <p className="text-xs text-white/30 font-mono mb-0.5 truncate pr-24">
        {twin.id.slice(0, 32)}…
      </p>
      <h3 className="font-semibold text-white text-sm mb-0.5">{twin.name}</h3>
      <p className="text-xs text-white/40 mb-3">{twin.product_type}</p>

      {showSoH && (
        <div className="flex items-center gap-4">
          <SoHGauge value={twin.current_soh_pct} size={64} label="SoH" />
          <div className="flex-1 space-y-1.5">
            {twin.current_capacity_kwh !== null && (
              <Metric label="Capacity" value={`${twin.current_capacity_kwh?.toFixed(1)} kWh`} />
            )}
            {twin.recyclability_score !== null && (
              <Metric label="Recyclability" value={`${twin.recyclability_score?.toFixed(0)} / 100`} />
            )}
            <Metric label="Version" value={`v${twin.version_id}`} />
          </div>
        </div>
      )}

      <div className="mt-3 flex items-center justify-between">
        <Link
          href={`/passport/${encodeURIComponent(twin.id)}`}
          className="text-[11px] text-purple-400 hover:text-purple-300 transition-colors"
          onClick={(e) => e.stopPropagation()}
        >
          View Passport →
        </Link>
        {twin.has_provenance_gap && (
          <span className="text-[10px] text-amber-400 flex items-center gap-1">
            <AlertTriangle size={10} /> Gap
          </span>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-[11px]">
      <span className="text-white/30">{label}</span>
      <span className="text-white/70 font-mono">{value}</span>
    </div>
  );
}
