/* Service worker: lets the resume open with no signal.
   VERSION is rewritten at deploy time by scripts/stamp_dates.py (commit date and
   short SHA), so every deploy gets a fresh cache and this site's old ones are
   deleted. Only caches named bsc-resume-* are ever touched: the github.io
   origin is shared with other project sites, whose caches must survive.
   Same-origin GETs go network-first (readers always get the newest page when
   online) and fall back to the cache; a navigation waits at most a few seconds
   for the network before using the cached copy, so a weak connection does not
   hang on a blank page. Cross-origin requests (the three.js / Vanta CDN on
   Home) and non-GET requests are never touched. */
const VERSION = 'bsc-dev';
const CACHE = 'bsc-resume-' + VERSION;
const NAV_TIMEOUT_MS = 4000;
const PRECACHE = [
  './', 'index.html', 'resume-atlas.html', 'resume-signal.html', 'proof-hub.html',
  'resume-switchboard.html', 'now.html', '404.html', 'offline.html',
  'shared-enhancements.js', 'cases.json', 'companies.json', 'resume-ats.txt',
  'brandon-clark.vcf', 'qr-resume.svg', 'favicon.svg', 'favicon.ico',
  'apple-touch-icon.png', 'icon-192.png', 'icon-512.png', 'icon-512-maskable.png',
  'site.webmanifest'
];

// Cache key: the URL without its query or hash, so ?plain=1, ?for=acme and
// similar variants share one entry instead of piling up.
function cacheKey(req) {
  const u = new URL(req.url);
  u.search = '';
  u.hash = '';
  return u.href;
}

self.addEventListener('install', (event) => {
  // Fetch each file on its own so one missing file never fails the install.
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      Promise.all(PRECACHE.map((url) =>
        fetch(new Request(url, { cache: 'reload' }))
          .then((res) => (res && res.ok ? cache.put(url, res) : null))
          .catch(() => null)
      ))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k.indexOf('bsc-resume-') === 0 && k !== CACHE).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// fetch() that gives up after `ms` so the cache fallback can take over.
function fetchWithTimeout(req, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('timeout')), ms);
    fetch(req).then((res) => { clearTimeout(timer); resolve(res); },
                    (err) => { clearTimeout(timer); reject(err); });
  });
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  const isNav = req.mode === 'navigate';
  const key = cacheKey(req);
  event.respondWith(
    (isNav ? fetchWithTimeout(req, NAV_TIMEOUT_MS) : fetch(req)).then((res) => {
      if (res && res.ok && res.type === 'basic') {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(key, copy)).catch(() => {});
      }
      return res;
    }).catch(() =>
      caches.match(key).then((hit) => {
        if (hit) return hit;
        if (isNav) {
          return caches.match('offline.html').then((o) => o || Response.error());
        }
        return Response.error();
      })
    )
  );
});
