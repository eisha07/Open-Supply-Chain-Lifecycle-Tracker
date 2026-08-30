// Technician Dashboard — the most feature-rich role view
"use client";

import { useState, useEffect, useCallback } from "react";
import { Wrench, Wifi, WifiOff, UploadCloud, Search, CheckCircle, XCircle } from "lucide-react";
import Link from "next/link";
import { listTwins, getTwin, appendEvent } from "@/lib/api";
import type { TwinRead, QueuedEvent } from "@/lib/types";
import { TwinCard } from "@/components/TwinCard";
import { EventTimeline } from "@/components/EventTimeline";
import { TelemetryPanel } from "@/components/TelemetryPanel";
import { SoHGauge } from "@/components/SoHGauge";

const LOCALSTORAGE_KEY = "oslt_offline_queue";

function loadQueue(): QueuedEvent[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(LOCALSTORAGE_KEY) ?? "[]"); }
  catch { return []; }
}

function saveQueue(q: QueuedEvent[]) {
  localStorage.setItem(LOCALSTORAGE_KEY, JSON.stringify(q));
}

export default function TechnicianDashboard() {
  const [twins, setTwins] = useState<TwinRead[]>([]);
  const [selectedTwin, setSelectedTwin] = useState<TwinRead | null>(null);
  const [queue, setQueue] = useState<QueuedEvent[]>([]);
  const [online, setOnline] = useState(true);
  const [syncResult, setSyncResult] = useState<{ accepted: number; rejected: number } | null>(null);
  const [loading, setLoading] = useState(false);

  // Load twins on mount
  useEffect(() => {
    listTwins({ limit: 50 }).then(setTwins).catch(() => {});
    setQueue(loadQueue());
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => { window.removeEventListener("online", handleOnline); window.removeEventListener("offline", handleOffline); };
  }, []);

  const handleSelectTwin = async (twin: TwinRead) => {
    const fresh = await getTwin(twin.id).catch(() => twin);
    setSelectedTwin(fresh);
  };

  const handleSyncQueue = async () => {
    const unsyncedEvents = queue.filter((e) => !e.synced);
    if (!unsyncedEvents.length) return;
    setLoading(true);
    let accepted = 0, rejected = 0;
    for (const qe of unsyncedEvents) {
      try {
        await appendEvent({
          twin_id: qe.twin_id,
          event_type: qe.event_type,
          actor_did: qe.actor_did,
          actor_timestamp: qe.actor_timestamp,
          metadata_json: qe.metadata_json,
          cryptographic_signature: qe.cryptographic_signature,
        });
        accepted++;
        const updated = queue.map((e) => e.id === qe.id ? { ...e, synced: true } : e);
        setQueue(updated);
        saveQueue(updated);
      } catch { rejected++; }
    }
    setLoading(false);
    setSyncResult({ accepted, rejected });
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Navbar */}
      <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Wrench size={18} className="text-amber-400" />
          <span className="font-semibold text-sm">Field Technician Dashboard</span>
        </div>
        <div className="flex items-center gap-4">
          <span className={`flex items-center gap-1.5 text-xs ${online ? "text-green-400" : "text-red-400"}`}>
            {online ? <Wifi size={12} /> : <WifiOff size={12} />}
            {online ? "Online" : "Offline — events queued locally"}
          </span>
          <Link href="/" className="text-xs text-white/30 hover:text-white/60 transition-colors">← Home</Link>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Twin list */}
        <aside>
          <h2 className="text-xs uppercase tracking-widest text-white/30 mb-4">Assets</h2>
          <div className="space-y-3 max-h-[calc(100vh-180px)] overflow-y-auto pr-1">
            {twins.length === 0 ? (
              <p className="text-xs text-white/25 text-center py-8">No twins found — check API connection.</p>
            ) : (
              twins.map((t) => (
                <TwinCard
                  key={t.id}
                  twin={t}
                  onClick={handleSelectTwin}
                />
              ))
            )}
          </div>
        </aside>

        {/* Centre: Twin detail */}
        <main className="lg:col-span-2 space-y-6">
          {selectedTwin ? (
            <>
              <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h1 className="text-lg font-bold text-white">{selectedTwin.name}</h1>
                    <p className="text-xs text-white/40">{selectedTwin.product_type} · v{selectedTwin.version_id}</p>
                  </div>
                  <SoHGauge value={selectedTwin.current_soh_pct} size={90} />
                </div>
                <p className="text-xs font-mono text-white/25 break-all">{selectedTwin.id}</p>
              </div>

              {/* Live telemetry */}
              <TelemetryPanel twinId={selectedTwin.id} />

              {/* Event history */}
              <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                <h3 className="text-sm font-semibold text-white mb-4">Event History</h3>
                <EventTimeline events={[]} />
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-white/20 gap-3">
              <Search size={32} />
              <p className="text-sm">Select an asset from the left to inspect it</p>
            </div>
          )}

          {/* Offline queue */}
          <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <UploadCloud size={15} className="text-cyan-400" />
                Offline Event Queue ({queue.filter((e) => !e.synced).length} pending)
              </h3>
              <button
                onClick={handleSyncQueue}
                disabled={loading || !online}
                className="text-xs px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 rounded-lg disabled:opacity-40 transition-colors"
              >
                {loading ? "Syncing…" : "Sync Now"}
              </button>
            </div>

            {syncResult && (
              <div className="flex gap-4 text-xs mb-3">
                <span className="flex items-center gap-1 text-green-400">
                  <CheckCircle size={11} /> {syncResult.accepted} accepted
                </span>
                <span className="flex items-center gap-1 text-red-400">
                  <XCircle size={11} /> {syncResult.rejected} rejected
                </span>
              </div>
            )}

            {queue.length === 0 ? (
              <p className="text-xs text-white/20 text-center py-4">Queue is empty</p>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {queue.map((qe) => (
                  <div key={qe.id} className="flex items-center justify-between bg-white/[0.02] rounded-lg px-3 py-2 text-xs">
                    <span className="text-white/50 font-mono">{qe.event_type}</span>
                    <span className={qe.synced ? "text-green-400" : "text-amber-400"}>
                      {qe.synced ? "Synced" : "Pending"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
