// Defect repair (F138 P16): this file previously implied more than it
// actually did, in both directions.
//
// (1) The app-shell/static-asset path (`/`, JS/CSS/images) matched
//     cache-first, but ASSETS_TO_CACHE only ever pre-populated '/' and
//     '/index.html' at install time - no JS/CSS bundle (their
//     filenames are content-hashed per build, so they can't be listed
//     here by name ahead of time) was ever actually written into the
//     cache anywhere in this file. That meant caches.match() for a
//     bundle file was always empty and every request fell through to
//     the network anyway - so despite serviceWorkerRegistration.js's
//     own comment claiming this "lets the app work offline", nothing
//     beyond the bare index.html document was ever actually available
//     without a network connection. Fixed below with a real
//     stale-while-revalidate-on-first-fetch: a same-origin static asset
//     that is fetched successfully gets written into the cache at that
//     point, so it - and only it, nothing pre-declared or guessed at -
//     is available offline on a later visit. This is still only the
//     app shell (HTML/JS/CSS/images), never business data - it does
//     not turn Woodful into an offline-capable ERP, which is
//     deliberately out of scope (see the F138 brief).
//
// (2) The `/api/` path's `fetch(request).catch(() => caches.match(...))`
//     read as if a failed API call could fall back to a cached
//     response - but nothing here ever wrote an API response into the
//     cache either, so that fallback could never resolve to real data.
//     It happened to be harmless (no stale/sensitive data was ever
//     actually served), but harmless-by-accident is not the same as
//     deliberately safe, and it invited a future edit to "fix" the
//     apparent gap by adding a cache.put() for API responses - which
//     would be a real defect: this app's /api/ responses include
//     authentication state, salary/payroll figures, and other
//     financial data that must never be served stale from a cache
//     after the network fails, silently presented as if current, nor
//     retained in Cache Storage indefinitely as an unmanaged, un-
//     encrypted copy of sensitive business data. Every /api/ request is
//     now explicitly network-only, with a clear thrown/rejected
//     failure (not a silently-served stale substitute) on a genuine
//     network error, so the calling code's own existing error/offline
//     handling (see utils/api.js, utils/utils.js's connectivity
//     watcher) is what decides what the user sees - this file must
//     never make that decision for them by quietly answering with old
//     data.
const CACHE_NAME = 'woodful-static-v2';
const PRECACHE_ASSETS = [
  '/',
  '/index.html',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;

  // Only ever GET is cacheable/safe to intercept at all - a mutation
  // must always reach the real network path untouched, with its real
  // success/failure surfaced to the caller, never silently answered
  // from this worker.
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);

  if (url.pathname.startsWith('/api/')) {
    // Network-only, deliberately. See the file-level comment (2) above
    // for why this must never fall back to a cached response - a
    // network failure here is left to reject normally, so the app's
    // own network-aware handling (utils/api.js, utils/utils.js)
    // decides what the user sees, rather than this worker silently
    // manufacturing an answer from old, possibly sensitive data.
    event.respondWith(fetch(request));
    return;
  }

  if (url.origin !== self.location.origin) {
    // Cross-origin requests (if any) are left entirely alone - not
    // this worker's concern to cache or intercept.
    return;
  }

  // Same-origin static asset (the app shell's HTML/JS/CSS/images):
  // serve from cache if already present, otherwise fetch from the
  // network and - only on a genuine success - store a copy for next
  // time. A failed fetch with nothing cached yet is left to fail
  // normally (there is no meaningful older copy to fall back to), so
  // this never invents content that was never actually loaded.
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (response && response.ok) {
          const responseCopy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, responseCopy));
        }
        return response;
      });
    })
  );
});
