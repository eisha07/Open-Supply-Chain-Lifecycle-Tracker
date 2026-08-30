// Live telemetry panel — connects to WebSocket and streams BMS data
"use client";

import { useEffect, useRef, useState } from "react";
import { createTelemetrySocket } from "@/lib/api";
import type { TelemetryReading } from "@/lib/types";
import { Activity, Wifi, WifiOff } from "lucide-react";

interface TelemetryPanelProps {
  twinId: string;
  className?: string;
}

const MAX_HISTORY = 60;

export function TelemetryPanel({ twinId, className = "" }: TelemetryPanelProps) {
  const [readings, setReadings] = useState<TelemetryReading[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    try {
      ws = createTelemetrySocket(twinId);
      wsRef.current = ws;

      ws.onopen = () => { setConnected(true); setError(null); };
      ws.onclose = () => setConnected(false);
      ws.onerror = () => { setConnected(false); setError("WebSocket error — is the backend running?"); };
      ws.onmessage = (e) => {
        try {
          const reading: TelemetryReading = JSON.parse(e.data);
          setReadings((prev) => [...prev.slice(-MAX_HISTORY + 1), reading]);
        } catch { /* ignore parse errors */ }
      };
    } catch {
      setError("Could not open WebSocket connection.");
    }

    return () => { ws?.close(); };
  }, [twinId]);

  const latest = readings[readings.length - 1];

  const stopStream = () => wsRef.current?.send(JSON.stringify({ command: "stop" }));

  return (
    <div className={`bg-white/[0.03] border border-white/5 rounded-2xl p-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity size={15} className="text-cyan-400" />
          <span className="text-sm font-semibold text-white">Live BMS Telemetry</span>
        </div>
        <div className="flex items-center gap-3">
          <span className={`flex items-center gap-1 text-[11px] ${connected ? "text-green-400" : "text-white/30"}`}>
            {connected ? <Wifi size={11} /> : <WifiOff size={11} />}
            {connected ? "Live" : "Disconnected"}
          </span>
          {connected && (
            <button
              onClick={stopStream}
              className="text-[11px] text-white/30 hover:text-white/60 transition-colors"
            >
              Stop
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="text-xs text-red-400 mb-3">{error}</p>
      )}

      {/* Latest reading */}
      {latest ? (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <TelemetryMetric label="SoH" value={`${latest.soh_pct.toFixed(1)}%`} color="#22c55e" />
          <TelemetryMetric label="Temp" value={`${latest.temperature_celsius}°C`} color="#f59e0b" />
          <TelemetryMetric label="Voltage" value={`${latest.voltage_v.toFixed(2)} V`} color="#06b6d4" />
          <TelemetryMetric label="Current" value={`${latest.current_a.toFixed(1)} A`} color="#8b5cf6" />
          <TelemetryMetric label="Cycles" value={String(latest.cycle_count)} color="#a78bfa" />
          <TelemetryMetric label="Readings" value={String(readings.length)} color="#6b7280" />
        </div>
      ) : (
        <div className="text-center py-6 text-white/20 text-xs">
          {connected ? "Waiting for first reading…" : "Not connected"}
        </div>
      )}

      {/* Mini sparkline — SoH history */}
      {readings.length > 1 && (
        <SparkLine values={readings.map((r) => r.soh_pct)} color="#22c55e" label="SoH trend" />
      )}
    </div>
  );
}

function TelemetryMetric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-white/[0.03] rounded-lg p-2.5">
      <p className="text-[10px] text-white/30 mb-0.5">{label}</p>
      <p className="text-sm font-mono font-semibold" style={{ color }}>{value}</p>
    </div>
  );
}

function SparkLine({ values, color, label }: { values: number[]; color: string; label: string }) {
  const W = 260, H = 40;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * W;
      const y = H - ((v - min) / range) * H;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div>
      <p className="text-[10px] text-white/25 mb-1">{label}</p>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} className="overflow-visible">
        <polyline
          points={pts}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          strokeLinejoin="round"
          opacity={0.8}
        />
      </svg>
    </div>
  );
}
