// Public Digital Product Passport — mobile-first, no auth required
"use client";

import { useEffect, useState, useCallback } from "react";
import { ShieldCheck, AlertTriangle, Info, Globe, QrCode, Download, ChevronLeft, ChevronRight, Filter } from "lucide-react";
import Link from "next/link";
import { getPublicPassport, getPublicTimeline, getPassportQrUrl } from "@/lib/api";
import type { TwinPublicRead, PassportTimeline, ComplianceBadge, EventType } from "@/lib/types";
import { SoHGauge } from "@/components/SoHGauge";
import { EventTimeline } from "@/components/EventTimeline";

const BADGE_COLORS: Record<string, string> = {
  green: "#22c55e",
  blue: "#3b82f6",
  teal: "#14b8a6",
  amber: "#f59e0b",
  red: "#ef4444",
  gray: "#6b7280",
};

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  ACTIVE:                              { text: "Active", color: "#22c55e" },
  PROVENANCE_GAP_DETECTED:             { text: "Provenance Gap", color: "#f59e0b" },
  TAMPERED_SAFETY_RISK:                { text: "Tamper Risk", color: "#ef4444" },
  UNSUITABLE_FOR_AUTOMOTIVE:           { text: "Not Automotive", color: "#f97316" },
  RECOMMENDED_FOR_STATIONARY_STORAGE:  { text: "Stationary Storage", color: "#06b6d4" },
  DECOMMISSIONED:                      { text: "Decommissioned", color: "#6b7280" },
  SCRAPPED:                            { text: "Scrapped", color: "#374151" },
};

const EVENT_TYPE_OPTIONS: { value: EventType | ""; label: string }[] = [
  { value: "", label: "All Events" },
  { value: "EXTRACTION", label: "Extraction" },
  { value: "ASSEMBLY", label: "Assembly" },
  { value: "CUSTODY_TRANSFER", label: "Custody Transfer" },
  { value: "REPAIR_PART_SWAP", label: "Repair / Part Swap" },
  { value: "TELEMETRY_SNAPSHOT", label: "Telemetry Snapshot" },
  { value: "DECOMMISSION", label: "Decommission" },
];

const PAGE_LIMIT = 20;

export default function PassportPage({ params }: { params: { twin_id: string } }) {
  const twinId = decodeURIComponent(params.twin_id);
  const [passport, setPassport] = useState<TwinPublicRead | null>(null);
  const [timeline, setTimeline] = useState<PassportTimeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showQr, setShowQr] = useState(false);

  // Timeline pagination + filtering
  const [page, setPage] = useState(0);
  const [eventTypeFilter, setEventTypeFilter] = useState<EventType | "">("");
  const [loadingTimeline, setLoadingTimeline] = useState(false);

  const loadTimeline = useCallback(async (currentPage: number, filter: EventType | "") => {
    setLoadingTimeline(true);
    try {
      const t = await getPublicTimeline(twinId, {
        limit: PAGE_LIMIT,
        offset: currentPage * PAGE_LIMIT,
        event_type: filter || undefined,
      });
      setTimeline(t);
    } catch {
      // keep existing timeline on filter error
    } finally {
      setLoadingTimeline(false);
    }
  }, [twinId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getPublicPassport(twinId),
      getPublicTimeline(twinId, { limit: PAGE_LIMIT, offset: 0 }),
    ]).then(([p, t]) => {
      setPassport(p);
      setTimeline(t);
    }).catch((err) => {
      setError(err instanceof Error ? err.message : "Passport not found");
    }).finally(() => setLoading(false));
  }, [twinId]);

  const handleFilterChange = async (filter: EventType | "") => {
    setEventTypeFilter(filter);
    setPage(0);
    await loadTimeline(0, filter);
  };

  const handlePageChange = async (newPage: number) => {
    setPage(newPage);
    await loadTimeline(newPage, eventTypeFilter);
  };

  const qrUrl = getPassportQrUrl(twinId, typeof window !== "undefined" ? window.location.origin : "http://localhost:3000");

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] text-white flex items-center justify-center">
        <div className="text-center space-y-2">
          <div className="w-8 h-8 border-2 border-white/10 border-t-white/60 rounded-full animate-spin mx-auto" />
          <p className="text-xs text-white/30">Loading Digital Product Passport…</p>
        </div>
      </div>
    );
  }

  if (error || !passport) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col items-center justify-center gap-4">
        <AlertTriangle size={40} className="text-red-400" />
        <h1 className="text-lg font-bold">Passport Not Found</h1>
        <p className="text-sm text-white/40">{error ?? "Unknown error"}</p>
        <Link href="/" className="text-xs text-blue-400 hover:text-blue-300">← Return home</Link>
      </div>
    );
  }

  const statusCfg = STATUS_LABEL[passport.status] ?? { text: passport.status, color: "#6b7280" };
  const pagination = timeline?.pagination;
  const totalPages = pagination ? Math.ceil(pagination.total / PAGE_LIMIT) : 1;

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white pb-16">
      {/* Header */}
      <header className="border-b border-white/5 px-5 py-4 flex items-center justify-between max-w-2xl mx-auto">
        <div className="flex items-center gap-2">
          <QrCode size={16} className="text-purple-400" />
          <span className="text-xs font-semibold text-white/70">Digital Product Passport</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowQr((v) => !v)}
            className="flex items-center gap-1.5 text-xs text-white/30 hover:text-white/60 transition-colors"
          >
            <QrCode size={13} /> QR Code
          </button>
          <Link href="/" className="text-xs text-white/30 hover:text-white/60 transition-colors">OSLT</Link>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-5 py-6 space-y-6">
        {/* QR Code panel */}
        {showQr && (
          <div className="bg-white/[0.03] border border-purple-500/20 rounded-2xl p-5 flex flex-col items-center gap-4">
            <p className="text-xs text-white/40">Scan to open this passport on any device</p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={qrUrl}
              alt="QR code for this passport"
              className="w-48 h-48 bg-white rounded-xl p-2"
              onError={(e) => (e.currentTarget.style.display = "none")}
            />
            <a
              href={qrUrl}
              download={`passport_qr_${twinId.slice(0, 20)}.png`}
              className="flex items-center gap-1.5 text-xs text-purple-300 hover:text-purple-200"
            >
              <Download size={12} /> Download PNG
            </a>
          </div>
        )}

        {/* Safety warnings */}
        {timeline?.safety_warnings?.map((w) => (
          <div
            key={w}
            className={`flex gap-2 rounded-xl p-3 text-xs leading-relaxed ${
              w.startsWith("CRITICAL") ? "bg-red-950/40 border border-red-500/20 text-red-300"
              : w.startsWith("WARNING") ? "bg-amber-950/30 border border-amber-500/20 text-amber-300"
              : "bg-white/[0.03] border border-white/5 text-white/50"
            }`}
          >
            <AlertTriangle size={14} className="flex-shrink-0 mt-0.5" />
            {w}
          </div>
        ))}

        {/* Product identity card */}
        <div className="bg-white/[0.04] border border-white/8 rounded-2xl p-5">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h1 className="text-xl font-bold text-white mb-0.5">{passport.name}</h1>
              <p className="text-sm text-white/40">{passport.product_type}</p>
              <span
                className="inline-flex items-center gap-1 mt-2 text-[11px] font-semibold px-2.5 py-1 rounded-full"
                style={{ background: statusCfg.color + "18", color: statusCfg.color }}
              >
                {statusCfg.text}
              </span>
            </div>
            <SoHGauge value={passport.current_soh_pct} size={88} label="SoH" />
          </div>

          <div className="grid grid-cols-2 gap-3 mt-4">
            <MetricTile label="Safety Rating" value={passport.current_safety_rating ?? "—"} color="#22c55e" />
            <MetricTile label="Recyclability" value={passport.recyclability_score !== null ? `${passport.recyclability_score}/100` : "—"} color="#14b8a6" />
            {passport.has_provenance_gap && (
              <div className="col-span-2 bg-amber-500/10 border border-amber-500/20 rounded-xl p-2.5 flex items-center gap-2 text-xs text-amber-300">
                <Info size={12} /> Provenance gap detected in this asset's supply chain history.
              </div>
            )}
          </div>
        </div>

        {/* Compliance badges */}
        {timeline?.compliance_badges && timeline.compliance_badges.length > 0 && (
          <div>
            <h2 className="text-xs uppercase tracking-widest text-white/30 mb-3">Compliance & Certifications</h2>
            <div className="flex flex-wrap gap-2">
              {timeline.compliance_badges.map((badge: ComplianceBadge) => (
                <div
                  key={badge.id}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border"
                  style={{
                    borderColor: (BADGE_COLORS[badge.color] ?? "#6b7280") + "40",
                    background: (BADGE_COLORS[badge.color] ?? "#6b7280") + "12",
                    color: BADGE_COLORS[badge.color] ?? "#6b7280",
                  }}
                >
                  <ShieldCheck size={11} />
                  {badge.label}
                  <span className="opacity-60">{badge.status}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Provenance timeline */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs uppercase tracking-widest text-white/30">
              Provenance Timeline
              {pagination && (
                <span className="ml-2 text-white/20 normal-case">
                  ({pagination.total} event{pagination.total !== 1 ? "s" : ""})
                </span>
              )}
            </h2>
            <div className="flex items-center gap-2">
              <Filter size={12} className="text-white/25" />
              <select
                value={eventTypeFilter}
                onChange={(e) => handleFilterChange(e.target.value as EventType | "")}
                className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-xs text-white focus:outline-none"
              >
                {EVENT_TYPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value} className="bg-zinc-900">{o.label}</option>
                ))}
              </select>
            </div>
          </div>

          {loadingTimeline ? (
            <div className="flex justify-center py-8">
              <div className="w-6 h-6 border-2 border-white/10 border-t-white/40 rounded-full animate-spin" />
            </div>
          ) : (
            <EventTimeline events={timeline?.timeline ?? []} />
          )}

          {/* Pagination controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 mt-4">
              <button
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 0 || loadingTimeline}
                className="flex items-center gap-1 text-xs text-white/40 hover:text-white/70 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft size={13} /> Prev
              </button>
              <span className="text-xs text-white/25">
                Page {page + 1} of {totalPages}
              </span>
              <button
                onClick={() => handlePageChange(page + 1)}
                disabled={!pagination?.has_more || loadingTimeline}
                className="flex items-center gap-1 text-xs text-white/40 hover:text-white/70 disabled:opacity-30 transition-colors"
              >
                Next <ChevronRight size={13} />
              </button>
            </div>
          )}
        </div>

        {/* DID */}
        <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
          <p className="text-[10px] text-white/25 mb-1 flex items-center gap-1.5">
            <Globe size={10} /> Digital Identity (DID)
          </p>
          <p className="text-[11px] font-mono text-white/40 break-all">{passport.id}</p>
        </div>
      </main>
    </div>
  );
}

function MetricTile({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-white/[0.03] rounded-xl p-3">
      <p className="text-[10px] text-white/30 mb-0.5">{label}</p>
      <p className="text-sm font-semibold" style={{ color }}>{value}</p>
    </div>
  );
}
