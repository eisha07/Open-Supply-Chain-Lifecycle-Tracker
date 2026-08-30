/**
 * OSLT Service Worker — Offline-First Support (Feature 8)
 *
 * Caches the public passport shell so field technicians can view previously
 * loaded passports without connectivity.  Queued events are stored in
 * localStorage (managed by the technician dashboard) and synced via
 * POST /telemetry/batch when back online.
 */

const CACHE_NAME = "oslt-v1";
const OFFLINE_ASSETS = [
  "/",
  "/dashboard/technician",
  "/_next/static/css/",
];

// ── Install: pre-cache shell ──────────────────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      cache.addAll(OFFLINE_ASSETS).catch(() => {}) // Best-effort; don't fail install
    )
  );
  self.skipWaiting();
});

// ── Activate: clean old caches ────────────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch: network-first with cache fallback ──────────────────────────────────
self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Don't intercept API calls or WebSocket upgrades
  if (
    request.url.includes("/api/") ||
    request.url.includes("localhost:8000") ||
    request.method !== "GET"
  ) {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        // Cache successful page navigations
        if (response.ok && request.destination === "document") {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, cloned));
        }
        return response;
      })
      .catch(() =>
        // Fall back to cache for offline access
        caches.match(request).then((cached) => cached ?? Response.error())
      )
  );
});

// ── Background sync: flush offline event queue ────────────────────────────────
self.addEventListener("sync", (event) => {
  if (event.tag === "oslt-sync-events") {
    event.waitUntil(syncOfflineEvents());
  }
});

async function syncOfflineEvents() {
  // The event queue lives in localStorage — accessed via the page context.
  // This background sync handler just pings the page to trigger the sync.
  const clients = await self.clients.matchAll({ type: "window" });
  clients.forEach((client) =>
    client.postMessage({ type: "OSLT_SYNC_REQUEST" })
  );
}
