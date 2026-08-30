// Reusable SoH Gauge component — displays State-of-Health as a circular arc
"use client";

interface SoHGaugeProps {
  value: number | null;   // 0–100
  size?: number;           // px
  label?: string;
}

const STATUS_COLOR: Record<string, string> = {
  good: "#22c55e",
  warn: "#f59e0b",
  bad: "#ef4444",
  unknown: "#6b7280",
};

function getColor(v: number | null) {
  if (v === null) return STATUS_COLOR.unknown;
  if (v >= 75) return STATUS_COLOR.good;
  if (v >= 40) return STATUS_COLOR.warn;
  return STATUS_COLOR.bad;
}

export function SoHGauge({ value, size = 120, label = "State of Health" }: SoHGaugeProps) {
  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = value ?? 0;
  const dash = (pct / 100) * circumference;
  const color = getColor(value);

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.07)"
          strokeWidth={8}
        />
        {/* Progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeDasharray={`${dash} ${circumference}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
        {/* Centre text */}
        <text
          x={size / 2}
          y={size / 2 + 1}
          textAnchor="middle"
          dominantBaseline="middle"
          fill={color}
          fontSize={size * 0.22}
          fontWeight="700"
          fontFamily="monospace"
        >
          {value !== null ? `${value.toFixed(0)}%` : "—"}
        </text>
      </svg>
      <p className="text-xs text-white/40 text-center">{label}</p>
    </div>
  );
}
