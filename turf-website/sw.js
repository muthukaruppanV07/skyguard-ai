/* GreenZone Arena — Service Worker (app shell + offline fallback) */

const CACHE = "gza-v1";
const APP_SHELL = [
  "/",
  "/index.html",
  "/admin.html",
  "/manifest.webmanifest",
  "/favicon.ico",
  "/robots.txt",
  "/sitemap.xml",
  "/css/style.css",
  "/css/admin.css",
  "/js/config.js",
  "/js/content.js",
  "/js/store.js",
  "/js/main.js",
  "/js/admin.js",
  "/assets/icons/icon-192.png",
  "/assets/icons/icon-512.png",
  "/assets/icons/icon-maskable-512.png",
  "/assets/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

/* Network-first, fall back to cache for same-origin assets.
   Bookings/payments stay client-side (localStorage), so this never
   interferes with checkout. Third-party calls (Razorpay, lucide,
   fonts, images) pass straight through. */
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== "GET") return;

  // Let cross-origin requests through untouched
  if (url.origin !== self.location.origin) {
    if (request.mode === "navigate") {
      event.respondWith(fetch(request));
    }
    return;
  }

  event.respondWith(
    (async () => {
      try {
        const fresh = await fetch(request);
        const copy = fresh.clone();
        caches
          .open(CACHE)
          .then((cache) => cache.put(request, copy))
          .catch(() => {});
        return fresh;
      } catch (err) {
        const cached = await caches.match(request, { ignoreSearch: true });
        if (cached) return cached;
        if (request.mode === "navigate") {
          const index = await caches.match("/index.html");
          if (index) return index;
        }
        throw err;
      }
    })(),
  );
});