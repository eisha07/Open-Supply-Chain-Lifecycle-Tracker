// API client for the Open Supply-Chain Lifecycle Tracker backend

import type {
  ActorKeypairOut,
  ActorRead,
  EventRead,
  PassportTimeline,
  RecyclingMatrix,
  SecondLifeEstimate,
  TwinRead,
  TwinPublicRead,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
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

export async function getActor(did: string): Promise<ActorRead> {
  return request(`/actors/${encodeURIComponent(did)}`);
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

// ── Events ────────────────────────────────────────────────────────────────────

export async function getEvents(
  twinId: string,
  limit = 100
): Promise<EventRead[]> {
  return request(
    `/events/${encodeURIComponent(twinId)}?limit=${limit}`
  );
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

// ── Public Passport ───────────────────────────────────────────────────────────

export async function getPublicPassport(
  twinId: string
): Promise<TwinPublicRead> {
  return request(`/passport/${encodeURIComponent(twinId)}`);
}

export async function getPublicTimeline(
  twinId: string
): Promise<PassportTimeline> {
  return request(`/passport/${encodeURIComponent(twinId)}/timeline`);
}

// ── Telemetry WebSocket ───────────────────────────────────────────────────────

export function createTelemetrySocket(twinId: string): WebSocket {
  const wsBase = BASE_URL.replace(/^http/, "ws");
  return new WebSocket(
    `${wsBase}/telemetry/ws/${encodeURIComponent(twinId)}`
  );
}
