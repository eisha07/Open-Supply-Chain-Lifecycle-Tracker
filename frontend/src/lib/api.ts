// API client for the Open Supply-Chain Lifecycle Tracker backend

import type {
  ActorKeypairOut,
  ActorRead,
  BlacklistedSerial,
  ChallengeResponse,
  EventRead,
  EventType,
  PassportTimeline,
  ProvenanceGapReport,
  RecyclingMatrix,
  SecondLifeEstimate,
  TokenResponse,
  TwinRead,
  TwinPublicRead,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  // Auto-attach JWT Bearer token if available
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("oslt_access_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  const res = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(String(err?.detail ?? "API error")), {
      status: res.status,
      detail: err?.detail,
    });
  }
  return res.json() as T;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function getChallenge(actorDid: string): Promise<ChallengeResponse> {
  return request(`/auth/challenge?actor_did=${encodeURIComponent(actorDid)}`);
}

export async function loginActor(
  actorDid: string,
  challenge: string,
  signature: string
): Promise<TokenResponse> {
  return request("/auth/token", {
    method: "POST",
    body: JSON.stringify({ actor_did: actorDid, challenge, signature }),
  });
}

export async function getMe(token: string): Promise<ActorRead> {
  return request("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

/** Clear stored JWT and actor info from localStorage. */
export function logout(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("oslt_access_token");
    localStorage.removeItem("oslt_actor_did");
    localStorage.removeItem("oslt_actor_role");
  }
}

/** Return the stored JWT token, or null if not logged in. */
export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("oslt_access_token");
}

/** Return the stored actor DID, or null if not logged in. */
export function getStoredActorDid(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("oslt_actor_did");
}

/** Return the stored actor role, or null if not logged in. */
export function getStoredActorRole(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("oslt_actor_role");
}

// ── Actors ────────────────────────────────────────────────────────────────────

export async function registerActor(
  display_name: string,
  role: string
): Promise<ActorKeypairOut> {
  return request("/actors", {
    method: "POST",
    body: JSON.stringify({ display_name, role }),
  });
}

export async function listActors(params?: {
  role?: string;
  is_blacklisted?: boolean;
  limit?: number;
  offset?: number;
}): Promise<ActorRead[]> {
  const qs = new URLSearchParams();
  if (params?.role) qs.set("role", params.role);
  if (params?.is_blacklisted !== undefined) qs.set("is_blacklisted", String(params.is_blacklisted));
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  return request(`/actors?${qs}`);
}

export async function getActor(did: string): Promise<ActorRead> {
  return request(`/actors/${encodeURIComponent(did)}`);
}

export async function blacklistActor(did: string, adminSecret: string): Promise<ActorRead> {
  return request(`/actors/${encodeURIComponent(did)}/blacklist`, {
    method: "POST",
    headers: { "X-Admin-Secret": adminSecret },
  });
}

// ── Twins ────────────────────────────────────────────────────────────────────

export async function listTwins(params?: {
  product_type?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<TwinRead[]> {
  const qs = new URLSearchParams();
  if (params?.product_type) qs.set("product_type", params.product_type);
  if (params?.status) qs.set("status", params.status);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  return request(`/twins?${qs}`);
}

export async function getTwin(twinId: string): Promise<TwinRead> {
  return request(`/twins/${encodeURIComponent(twinId)}`);
}

export async function getTwinChildren(twinId: string): Promise<TwinRead[]> {
  return request(`/twins/${encodeURIComponent(twinId)}/children`);
}

export async function createTwin(
  actorDid: string,
  payload: {
    name: string;
    product_type: string;
    parent_twin_id?: string;
    serial_number?: string;
    manufacturing_date?: string;
    material_weights_kg?: Record<string, number>;
    baseline_chemistry?: Record<string, number>;
    initial_capacity_kwh?: number;
    initial_safety_rating?: string;
  }
): Promise<TwinRead> {
  return request(`/twins?actor_did=${encodeURIComponent(actorDid)}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getSecondLifeEstimate(
  twinId: string
): Promise<SecondLifeEstimate> {
  return request(`/twins/${encodeURIComponent(twinId)}/second-life`);
}

export async function getRecyclingMatrix(
  twinId: string
): Promise<RecyclingMatrix> {
  return request(`/twins/${encodeURIComponent(twinId)}/recycling`);
}

export async function generateZkpFlags(
  twinId: string,
  actorDid: string,
  claims: Record<string, unknown>
): Promise<{ twin_id: string; zkp_flags: Record<string, unknown> }> {
  return request(
    `/twins/${encodeURIComponent(twinId)}/zkp?actor_did=${encodeURIComponent(actorDid)}`,
    { method: "POST", body: JSON.stringify({ claims }) }
  );
}

export async function getProvenanceGaps(twinId: string): Promise<ProvenanceGapReport> {
  return request(`/twins/${encodeURIComponent(twinId)}/provenance-gaps`);
}

// ── Events ────────────────────────────────────────────────────────────────────

export async function getEvents(
  twinId: string,
  params?: {
    limit?: number;
    offset?: number;
    event_type?: EventType;
    actor_did?: string;
    date_from?: string;
    date_to?: string;
  }
): Promise<EventRead[]> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  if (params?.event_type) qs.set("event_type", params.event_type);
  if (params?.actor_did) qs.set("actor_did", params.actor_did);
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  return request(`/events/${encodeURIComponent(twinId)}?${qs}`);
}

export async function appendEvent(payload: {
  twin_id: string;
  event_type: string;
  actor_did: string;
  actor_timestamp: string;
  metadata_json: Record<string, unknown>;
  cryptographic_signature: string;
  expected_version?: number;
}): Promise<EventRead> {
  return request("/events", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function exportEventsCsvUrl(
  twinId: string,
  params?: { event_type?: string; actor_did?: string }
): string {
  const qs = new URLSearchParams();
  if (params?.event_type) qs.set("event_type", params.event_type);
  if (params?.actor_did) qs.set("actor_did", params.actor_did);
  const queryStr = qs.toString();
  return `${BASE_URL}/events/${encodeURIComponent(twinId)}/export${queryStr ? `?${queryStr}` : ""}`;
}

// ── Public Passport ───────────────────────────────────────────────────────────

export async function getPublicPassport(
  twinId: string
): Promise<TwinPublicRead> {
  return request(`/passport/${encodeURIComponent(twinId)}`);
}

export async function getPublicTimeline(
  twinId: string,
  params?: { limit?: number; offset?: number; event_type?: string }
): Promise<PassportTimeline> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  if (params?.event_type) qs.set("event_type", params.event_type);
  return request(`/passport/${encodeURIComponent(twinId)}/timeline?${qs}`);
}

export function getPassportQrUrl(twinId: string, baseUrl?: string): string {
  const qs = new URLSearchParams();
  if (baseUrl) qs.set("base_url", baseUrl);
  return `${BASE_URL}/passport/${encodeURIComponent(twinId)}/qr?${qs}`;
}

// ── Counterfeit Serials ───────────────────────────────────────────────────────

export async function listBlacklistedSerials(): Promise<BlacklistedSerial[]> {
  return request("/serials");
}

export async function addBlacklistedSerial(
  serial_number: string,
  reason: string,
  adminSecret: string,
  added_by_did?: string
): Promise<BlacklistedSerial> {
  return request("/serials", {
    method: "POST",
    headers: { "X-Admin-Secret": adminSecret },
    body: JSON.stringify({ serial_number, reason, added_by_did }),
  });
}

export async function removeBlacklistedSerial(
  serial_number: string,
  adminSecret: string
): Promise<void> {
  await fetch(`${BASE_URL}/serials/${encodeURIComponent(serial_number)}`, {
    method: "DELETE",
    headers: { "X-Admin-Secret": adminSecret },
  });
}

// ── Telemetry WebSocket ───────────────────────────────────────────────────────

export function createTelemetrySocket(twinId: string): WebSocket {
  const wsBase = BASE_URL.replace(/^http/, "ws");
  return new WebSocket(
    `${wsBase}/telemetry/ws/${encodeURIComponent(twinId)}`
  );
}
