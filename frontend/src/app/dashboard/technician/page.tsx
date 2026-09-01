// Technician Dashboard — event timeline wired, event submission form, offline queue
"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Wrench, Wifi, WifiOff, UploadCloud, Search,
  CheckCircle, XCircle, Plus, Send, Loader, Download,
} from "lucide-react";
import Link from "next/link";
import { listTwins, getTwin, appendEvent, getEvents, exportEventsCsvUrl } from "@/lib/api";
import type { TwinRead, QueuedEvent, EventRead, EventType } from "@/lib/types";
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

// Supported event types for technicians
const TECH_EVENT_TYPES: EventType[] = [
  "TELEMETRY_SNAPSHOT",
  "REPAIR_PART_SWAP",
  "CUSTODY_TRANSFER",
];

const EVENT_TYPE_LABELS: Record<string, string> = {
  TELEMETRY_SNAPSHOT: "Telemetry Snapshot",
  REPAIR_PART_SWAP: "Repair / Part Swap",
  CUSTODY_TRANSFER: "Custody Transfer",
};

// Default metadata templates per event type
const METADATA_TEMPLATES: Record<string, Record<string, string>> = {
  TELEMETRY_SNAPSHOT: { soh_pct: "95", temperature_celsius: "25", voltage_v: "3.7", current_a: "10" },
  REPAIR_PART_SWAP: { new_part_serial: "", repair_type: "cell_replacement", event_notes: "" },
  CUSTODY_TRANSFER: { custody_region: "", event_notes: "" },
};

export default function TechnicianDashboard() {
  const [twins, setTwins] = useState<TwinRead[]>([]);
  const [selectedTwin, setSelectedTwin] = useState<TwinRead | null>(null);
  const [events, setEvents] = useState<EventRead[]>([]);
  const [queue, setQueue] = useState<QueuedEvent[]>([]);
  const [online, setOnline] = useState(true);
  const [syncResult, setSyncResult] = useState<{ accepted: number; rejected: number } | null>(null);
  const [loadingTwins, setLoadingTwins] = useState(true);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [syncing, setSyncing] = useState(false);

  // Event submission form state
  const [showEventForm, setShowEventForm] = useState(false);
  const [eventForm, setEventForm] = useState({
    event_type: "TELEMETRY_SNAPSHOT" as EventType,
    actor_did: "",
    private_key_hex: "",
    metadata_raw: JSON.stringify(METADATA_TEMPLATES.TELEMETRY_SNAPSHOT, null, 2),
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  // Event filter
  const [eventTypeFilter, setEventTypeFilter] = useState<EventType | "">("");

  useEffect(() => {
    setLoadingTwins(true);
    listTwins({ limit: 50 })
      .then(setTwins)
      .catch(() => {})
      .finally(() => setLoadingTwins(false));
    setQueue(loadQueue());
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const loadEvents = useCallback(async (twinId: string, typeFilter?: EventType | "") => {
    setLoadingEvents(true);
    try {
      const data = await getEvents(twinId, {
        limit: 100,
        event_type: typeFilter || undefined,
      });
      setEvents(data);
    } catch {
      setEvents([]);
    } finally {
      setLoadingEvents(false);
    }
  }, []);

  const handleSelectTwin = async (twin: TwinRead) => {
    const fresh = await getTwin(twin.id).catch(() => twin);
    setSelectedTwin(fresh);
    setShowEventForm(false);
    setSubmitSuccess(false);
    setSubmitError(null);
    await loadEvents(fresh.id, eventTypeFilter);
  };

  const handleEventTypeFilter = async (type: EventType | "") => {
    setEventTypeFilter(type);
    if (selectedTwin) await loadEvents(selectedTwin.id, type);
  };

  // Sign event with Ed25519 private key in browser.
  // Cast to `any` because TypeScript's dom lib doesn't yet include Ed25519 in SubtleCrypto types.
  async function signEventPayload(payload: Record<string, unknown>, privateKeyHex: string): Promise<string> {
    const subtle = crypto.subtle as any; // eslint-disable-line @typescript-eslint/no-explicit-any
    const privateKeyBytes = hexToBytes(privateKeyHex);
    const cryptoKey = await subtle.importKey("raw", privateKeyBytes, "Ed25519", false, ["sign"]);
    const canonical = JSON.stringify(payload, Object.keys(payload).sort());
    const msgBytes = new TextEncoder().encode(canonical);
    const sigBytes = await subtle.sign("Ed25519", cryptoKey, msgBytes);
    return bytesToBase64Url(new Uint8Array(sigBytes));
  }

  const handleSubmitEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTwin) return;
    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(false);

    try {
      const metadata = JSON.parse(eventForm.metadata_raw);
      const actorTimestamp = new Date().toISOString();

      const canonicalPayload = {
        twin_id: selectedTwin.id,
        event_type: eventForm.event_type,
        actor_did: eventForm.actor_did,
        actor_timestamp: actorTimestamp,
        metadata_json: metadata,
      };
      const signature = await signEventPayload(canonicalPayload, eventForm.private_key_hex);

      if (!online) {
        // Queue for later sync
        const queuedEvent: QueuedEvent = {
          id: crypto.randomUUID(),
          twin_id: selectedTwin.id,
          event_type: eventForm.event_type,
          actor_did: eventForm.actor_did,
          actor_timestamp: actorTimestamp,
          metadata_json: metadata,
          cryptographic_signature: signature,
          queued_at: new Date().toISOString(),
          synced: false,
        };
        const updatedQueue = [...queue, queuedEvent];
        setQueue(updatedQueue);
        saveQueue(updatedQueue);
        setSubmitSuccess(true);
        setShowEventForm(false);
      } else {
        await appendEvent({
          twin_id: selectedTwin.id,
          event_type: eventForm.event_type,
          actor_did: eventForm.actor_did,
          actor_timestamp: actorTimestamp,
          metadata_json: metadata,
          cryptographic_signature: signature,
          expected_version: selectedTwin.version_id,
        });
        setSubmitSuccess(true);
        setShowEventForm(false);
        // Refresh events and twin
        const fresh = await getTwin(selectedTwin.id).catch(() => selectedTwin);
        setSelectedTwin(fresh);
        await loadEvents(fresh.id, eventTypeFilter);
      }
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSyncQueue = async () => {
    const unsynced = queue.filter((e) => !e.synced);
    if (!unsynced.length) return;
    setSyncing(true);
    let accepted = 0, rejected = 0;
    for (const qe of unsynced) {
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
    setSyncing(false);
    setSyncResult({ accepted, rejected });
    if (selectedTwin) await loadEvents(selectedTwin.id, eventTypeFilter);
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
          {loadingTwins ? (
            <div className="flex justify-center py-8">
              <Loader size={20} className="animate-spin text-white/20" />
            </div>
          ) : twins.length === 0 ? (
            <p className="text-xs text-white/25 text-center py-8">No twins found — check API connection.</p>
          ) : (
            <div className="space-y-3 max-h-[calc(100vh-180px)] overflow-y-auto pr-1">
              {twins.map((t) => (
                <TwinCard key={t.id} twin={t} onClick={handleSelectTwin} />
              ))}
            </div>
          )}
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
                {submitSuccess && (
                  <div className="mt-3 flex items-center gap-2 text-xs text-green-400 bg-green-950/30 border border-green-500/20 rounded-lg px-3 py-2">
                    <CheckCircle size={12} /> Event submitted successfully
                  </div>
                )}
              </div>

              {/* Live telemetry */}
              <TelemetryPanel twinId={selectedTwin.id} />

              {/* Event history */}
              <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-white">Event History</h3>
                  <div className="flex items-center gap-2">
                    <select
                      value={eventTypeFilter}
                      onChange={(e) => handleEventTypeFilter(e.target.value as EventType | "")}
                      className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-xs text-white focus:outline-none"
                    >
                      <option value="" className="bg-zinc-900">All Types</option>
                      {TECH_EVENT_TYPES.map((t) => (
                        <option key={t} value={t} className="bg-zinc-900">{EVENT_TYPE_LABELS[t] ?? t}</option>
                      ))}
                    </select>
                    <a
                      href={exportEventsCsvUrl(selectedTwin.id)}
                      download
                      className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 bg-white/5 hover:bg-white/10 text-white/50 hover:text-white/80 rounded-lg transition-colors"
                    >
                      <Download size={11} /> CSV
                    </a>
                    <button
                      onClick={() => setShowEventForm((v) => !v)}
                      className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 rounded-lg transition-colors"
                    >
                      <Plus size={11} /> Add Event
                    </button>
                  </div>
                </div>

                {/* Event submission form */}
                {showEventForm && (
                  <form onSubmit={handleSubmitEvent} className="mb-4 bg-white/[0.03] border border-amber-500/15 rounded-xl p-4 space-y-3">
                    <h4 className="text-xs font-semibold text-amber-300 mb-2">Submit Lifecycle Event</h4>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[10px] text-white/30 mb-1">Event Type</label>
                        <select
                          value={eventForm.event_type}
                          onChange={(e) => {
                            const t = e.target.value as EventType;
                            setEventForm((f) => ({
                              ...f,
                              event_type: t,
                              metadata_raw: JSON.stringify(METADATA_TEMPLATES[t] ?? {}, null, 2),
                            }));
                          }}
                          className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none"
                        >
                          {TECH_EVENT_TYPES.map((t) => (
                            <option key={t} value={t} className="bg-zinc-900">{EVENT_TYPE_LABELS[t]}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] text-white/30 mb-1">Actor DID</label>
                        <input
                          value={eventForm.actor_did}
                          onChange={(e) => setEventForm((f) => ({ ...f, actor_did: e.target.value }))}
                          placeholder="did:key:z6Mk…"
                          required
                          className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-white/15 focus:outline-none"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-[10px] text-white/30 mb-1">Private Key (hex) — used for signing only, not stored</label>
                      <input
                        type="password"
                        value={eventForm.private_key_hex}
                        onChange={(e) => setEventForm((f) => ({ ...f, private_key_hex: e.target.value }))}
                        placeholder="64-char hex private key"
                        required
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-white/15 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-[10px] text-white/30 mb-1">Metadata (JSON)</label>
                      <textarea
                        value={eventForm.metadata_raw}
                        onChange={(e) => setEventForm((f) => ({ ...f, metadata_raw: e.target.value }))}
                        rows={4}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs font-mono text-white/80 focus:outline-none resize-none"
                      />
                    </div>

                    {submitError && (
                      <p className="text-xs text-red-400">{submitError}</p>
                    )}

                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={submitting}
                        className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 rounded-lg disabled:opacity-50 transition-colors"
                      >
                        {submitting ? <Loader size={11} className="animate-spin" /> : <Send size={11} />}
                        {submitting ? "Signing & Submitting…" : online ? "Sign & Submit" : "Queue Offline"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowEventForm(false)}
                        className="text-xs px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}

                {loadingEvents ? (
                  <div className="flex justify-center py-6">
                    <Loader size={18} className="animate-spin text-white/20" />
                  </div>
                ) : (
                  <EventTimeline events={events} />
                )}
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
                disabled={syncing || !online}
                className="text-xs px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 rounded-lg disabled:opacity-40 transition-colors flex items-center gap-1.5"
              >
                {syncing ? <Loader size={11} className="animate-spin" /> : null}
                {syncing ? "Syncing…" : "Sync Now"}
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

// ── Browser crypto helpers ────────────────────────────────────────────────────

function hexToBytes(hex: string): Uint8Array {
  const arr = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) arr[i / 2] = parseInt(hex.slice(i, i + 2), 16);
  return arr;
}

function bytesToBase64Url(bytes: Uint8Array): string {
  let b = "";
  bytes.forEach((byte) => (b += String.fromCharCode(byte)));
  return btoa(b).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}
