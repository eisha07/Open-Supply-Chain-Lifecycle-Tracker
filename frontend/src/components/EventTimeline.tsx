// Event timeline — shows an ordered list of lifecycle events with icons
"use client";

import type { EventRead, EventPublicRead } from "@/lib/types";
import {
  Pickaxe, Cpu, ArrowRightLeft, Wrench, Activity,
  Trash2, AlertTriangle, Info,
} from "lucide-react";

type AnyEvent = EventRead | EventPublicRead;

const EVENT_META: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  EXTRACTION:          { icon: <Pickaxe size={14} />,       color: "#22c55e", label: "Extraction" },
  ASSEMBLY:            { icon: <Cpu size={14} />,            color: "#3b82f6", label: "Assembly" },
  CUSTODY_TRANSFER:    { icon: <ArrowRightLeft size={14} />, color: "#a78bfa", label: "Custody Transfer" },
  REPAIR_PART_SWAP:    { icon: <Wrench size={14} />,         color: "#f59e0b", label: "Repair / Part Swap" },
  TELEMETRY_SNAPSHOT:  { icon: <Activity size={14} />,       color: "#06b6d4", label: "Telemetry Snapshot" },
  DECOMMISSION:        { icon: <Trash2 size={14} />,         color: "#6b7280", label: "Decommission" },
  SECURITY_ALERT:      { icon: <AlertTriangle size={14} />,  color: "#ef4444", label: "Security Alert" },
  PROVENANCE_GAP_AUDIT:{ icon: <Info size={14} />,           color: "#f59e0b", label: "Provenance Gap" },
};

function isPublic(e: AnyEvent): e is EventPublicRead {
  return "actor_did_masked" in e;
}

interface EventTimelineProps {
  events: AnyEvent[];
  className?: string;
}

export function EventTimeline({ events, className = "" }: EventTimelineProps) {
  if (!events.length) {
    return (
      <div className={`text-center py-10 text-white/30 text-sm ${className}`}>
        No events recorded yet.
      </div>
    );
  }

  return (
    <ol className={`relative border-l border-white/10 pl-6 space-y-5 ${className}`}>
      {events.map((event) => {
        const meta = EVENT_META[event.event_type] ?? EVENT_META.EXTRACTION;
        const actorDisplay = isPublic(event) ? event.actor_did_masked :
          event.actor_did.slice(0, 24) + "…";
        const ts = new Date(event.actor_timestamp).toLocaleString();

        return (
          <li key={event.id} className="relative">
            {/* Dot */}
            <span
              className="absolute -left-[29px] top-0.5 w-4 h-4 rounded-full flex items-center justify-center"
              style={{ background: meta.color + "22", border: `1px solid ${meta.color}44` }}
            >
              <span style={{ color: meta.color }}>{meta.icon}</span>
            </span>

            <div className="bg-white/[0.03] border border-white/5 rounded-xl p-3">
              <div className="flex items-center justify-between mb-1">
                <span
                  className="text-xs font-semibold px-2 py-0.5 rounded-full"
                  style={{ background: meta.color + "18", color: meta.color }}
                >
                  {meta.label}
                </span>
                <span className="text-xs text-white/25 font-mono">#{event.sequence_num}</span>
              </div>

              <p className="text-xs text-white/40 mb-1">
                <span className="font-mono text-white/25">{actorDisplay}</span>
                {" · "}
                {ts}
              </p>

              {/* Metadata preview */}
              {isPublic(event)
                ? Object.keys(event.public_metadata).length > 0 && (
                    <MetaChips data={event.public_metadata} />
                  )
                : Object.keys(event.metadata_json).length > 0 && (
                    <MetaChips data={event.metadata_json} />
                  )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function MetaChips({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).slice(0, 4);
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {entries.map(([k, v]) => (
        <span
          key={k}
          className="text-[10px] bg-white/5 text-white/40 px-2 py-0.5 rounded-full font-mono"
        >
          {k}: {String(v)}
        </span>
      ))}
    </div>
  );
}
