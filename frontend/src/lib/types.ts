// TypeScript type definitions for the OSLT API

export type ActorRole =
  | "RAW_MATERIAL_SUPPLIER"
  | "OEM_MANUFACTURER"
  | "FIELD_TECHNICIAN"
  | "RECYCLER_DISMANTLER"
  | "PUBLIC";

export type TwinStatus =
  | "ACTIVE"
  | "PROVENANCE_GAP_DETECTED"
  | "TAMPERED_SAFETY_RISK"
  | "UNSUITABLE_FOR_AUTOMOTIVE"
  | "RECOMMENDED_FOR_STATIONARY_STORAGE"
  | "DECOMMISSIONED"
  | "SCRAPPED";

export type EventType =
  | "EXTRACTION"
  | "ASSEMBLY"
  | "CUSTODY_TRANSFER"
  | "REPAIR_PART_SWAP"
  | "TELEMETRY_SNAPSHOT"
  | "DECOMMISSION"
  | "SECURITY_ALERT"
  | "PROVENANCE_GAP_AUDIT";

// ── Actor ────────────────────────────────────────────────────────────────────

export interface ActorRead {
  did: string;
  display_name: string;
  role: ActorRole;
  is_blacklisted: boolean;
  created_at: string;
}

export interface ActorKeypairOut {
  actor: ActorRead;
  private_key_hex: string;
  public_key_hex: string;
  did: string;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface ChallengeResponse {
  challenge: string;
  actor_did: string;
  expires_in_seconds: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  actor: ActorRead;
}

// ── Digital Twin ─────────────────────────────────────────────────────────────

export interface TwinRead {
  id: string;
  name: string;
  product_type: string;
  parent_twin_id: string | null;
  status: TwinStatus;
  version_id: number;
  manufacturer_did: string;
  manufacturing_date: string | null;
  serial_number: string | null;
  material_weights_kg: Record<string, number> | null;
  baseline_chemistry: Record<string, number> | null;
  initial_capacity_kwh: number | null;
  current_capacity_kwh: number | null;
  current_soh_pct: number | null;
  current_chemistry: Record<string, number> | null;
  current_safety_rating: string | null;
  recyclability_score: number | null;
  zkp_flags: Record<string, unknown> | null;
  has_provenance_gap: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface TwinPublicRead {
  id: string;
  name: string;
  product_type: string;
  status: TwinStatus;
  current_soh_pct: number | null;
  current_safety_rating: string | null;
  recyclability_score: number | null;
  zkp_flags: Record<string, unknown> | null;
  has_provenance_gap: boolean;
  created_at: string;
}

// ── Events ────────────────────────────────────────────────────────────────────

export interface EventRead {
  id: number;
  twin_id: string;
  event_type: EventType;
  sequence_num: number;
  actor_did: string;
  actor_timestamp: string;
  server_timestamp: string;
  metadata_json: Record<string, unknown>;
  cryptographic_signature: string;
  previous_event_hash: string | null;
}

export interface EventPublicRead {
  id: number;
  twin_id: string;
  event_type: EventType;
  sequence_num: number;
  actor_did_masked: string;
  actor_timestamp: string;
  public_metadata: Record<string, unknown>;
}

// ── Passport ─────────────────────────────────────────────────────────────────

export interface ComplianceBadge {
  id: string;
  label: string;
  status: string;
  color: string;
}

export interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface PassportTimeline {
  twin_id: string;
  product_name: string;
  product_type: string;
  status: TwinStatus;
  timeline: EventPublicRead[];
  pagination: PaginationMeta;
  compliance_badges: ComplianceBadge[];
  safety_warnings: string[];
}

// ── Second Life ───────────────────────────────────────────────────────────────

export interface SecondLifeEstimate {
  twin_id: string;
  current_soh_pct: number | null;
  recommendation: string;
  suitable_for_automotive: boolean;
  suitable_for_stationary_storage: boolean;
  reasoning: string;
}

// ── Recycling ────────────────────────────────────────────────────────────────

export interface HazardousMaterial {
  material: string;
  estimated_weight_kg: number | string;
  hazard_class: string;
  ppe_required: string;
  disposal: string;
}

export interface TargetMetal {
  metal: string;
  gross_weight_kg: number;
  recoverable_kg: number;
  recovery_purity_pct: number;
  estimated_value_usd: number;
}

export interface RecyclingMatrix {
  twin_id: string;
  product_type: string;
  current_soh_pct: number | null;
  hazardous_materials: HazardousMaterial[];
  target_metals: TargetMetal[];
  estimated_recovery_value_usd: number;
  disassembly_sequence: { step: number; action: string }[];
  regulatory_references: string[];
}

// ── Counterfeit Serials ───────────────────────────────────────────────────────

export interface BlacklistedSerial {
  id: number;
  serial_number: string;
  reason: string | null;
  added_by_did: string | null;
}

// ── IoT Telemetry ─────────────────────────────────────────────────────────────

export interface TelemetryReading {
  twin_id: string;
  timestamp: string;
  soh_pct: number;
  temperature_celsius: number;
  voltage_v: number;
  current_a: number;
  cycle_count: number;
}

// ── Offline Queue ────────────────────────────────────────────────────────────

export interface QueuedEvent {
  id: string;          // local UUID
  twin_id: string;
  event_type: EventType;
  actor_did: string;
  actor_timestamp: string;
  metadata_json: Record<string, unknown>;
  cryptographic_signature: string;
  queued_at: string;
  synced: boolean;
}

// ── Provenance Gaps ───────────────────────────────────────────────────────────

export interface ProvenanceGap {
  after_sequence: number;
  before_sequence: number;
  missing_sequences: number[];
  gap_size: number;
  after_event_type: EventType;
  before_event_type: EventType;
  after_actor_did: string;
  before_actor_did: string;
  after_timestamp: string;
  before_timestamp: string;
}

export interface ProvenanceGapReport {
  twin_id: string;
  has_provenance_gap: boolean;
  total_events_recorded: number;
  total_gaps: number;
  total_missing_events: number;
  gaps: ProvenanceGap[];
  recommendation: string;
}
