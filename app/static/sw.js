// Service Worker for VoterList PWA (Nokor Pheas Commune)
const CACHE_NAME = 'voterlist-cache-v5.0';

// Assets to precache for offline resiliency
const PRECACHE_ASSETS = [
  '/static/css/style.css?v=30.0',
  '/static/js/app.js?v=3.1',
  '/static/js/khmer_id_ocr.js?v=3.1',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/icons/apple-touch-icon.png',
  '/favicon.ico'
];

// Modern Offline / Server-Not-Running Fallback Screen
const OFFLINE_HTML = `<!DOCTYPE html>
<html lang="km">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>រង់ចាំការតភ្ជាប់ Server - រដ្ឋបាលឃុំនគរភាស</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Khmer OS Siemreap", "Khmer OS Battambang", sans-serif;
      background: radial-gradient(circle at top, #1e3a8a 0%, #0f172a 100%);
      color: #f8fafc;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 20px;
    }
    .card {
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 24px;
      padding: 36px 28px;
      max-width: 520px;
      width: 100%;
      text-align: center;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
    }
    .logo-badge {
      width: 80px;
      height: 80px;
      margin: 0 auto 16px;
      border-radius: 20px;
      background: rgba(30, 58, 138, 0.5);
      border: 2px solid #f59e0b;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 38px;
      box-shadow: 0 10px 25px rgba(245, 158, 11, 0.2);
    }
    .pulse-ring {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.4);
      color: #fca5a5;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 16px;
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background: #ef4444;
      border-radius: 50%;
      animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.9); opacity: 0.7; }
      50% { transform: scale(1.3); opacity: 1; }
      100% { transform: scale(0.9); opacity: 0.7; }
    }
    h1 {
      font-size: 20px;
      font-weight: 700;
      color: #ffffff;
      margin-bottom: 6px;
      line-height: 1.4;
    }
    .subtitle {
      color: #fbbf24;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 18px;
    }
    .guide-box {
      background: rgba(30, 41, 59, 0.7);
      border: 1px solid rgba(148, 163, 184, 0.15);
      border-radius: 16px;
      padding: 16px 18px;
      text-align: left;
      margin-bottom: 22px;
      font-size: 13px;
      line-height: 1.6;
      color: #cbd5e1;
    }
    .guide-box ol {
      margin-left: 20px;
      margin-top: 8px;
    }
    .guide-box li {
      margin-bottom: 6px;
    }
    .code-tag {
      background: #0b1329;
      color: #38bdf8;
      padding: 2px 6px;
      border-radius: 6px;
      font-family: monospace;
      font-size: 12px;
    }
    .status-poll {
      font-size: 12px;
      color: #94a3b8;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      margin-bottom: 18px;
    }
    .spinner {
      width: 14px;
      height: 14px;
      border: 2px solid #38bdf8;
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
      color: #ffffff;
      padding: 13px 20px;
      border-radius: 14px;
      border: none;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s;
      box-shadow: 0 10px 20px rgba(37, 99, 235, 0.3);
    }
    .btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 12px 24px rgba(37, 99, 235, 0.4);
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo-badge">🏛️</div>
    <div class="pulse-ring">
      <span class="pulse-dot"></span>
      <span>មិនទាន់ភ្ជាប់ទៅកាន់ Server</span>
    </div>
    <h1>រដ្ឋបាលឃុំនគរភាស</h1>
    <p class="subtitle">ប្រព័ន្ធគ្រប់គ្រងទិន្នន័យអ្នកចុះឈ្មោះបោះឆ្នោត</p>

    <div class="guide-box">
      <strong>⚠️ មូលហេតុ៖</strong> កម្មវិធី Server នៅលើកុំព្យូទ័រមិនទាន់ត្រូវបានបើកដំណើរការ ឬកំពុងចាប់ផ្តើម។
      <ol>
        <li>សូមពិនិត្យមើលផ្ទាំង <span class="code-tag">run.bat</span> ក្នុង Folder <span class="code-tag">VoterList</span>។</li>
        <li>ប្រសិនបើមិនទាន់បានបើក សូមចុចពីរដង (Double click) លើ <span class="code-tag">run.bat</span> ដើម្បីចាប់ផ្ដើម។</li>
        <li>នៅពេល Server ដំណើរការរួចរាល់ ផ្ទាំងនេះនឹង <strong>Reload ចូលប្រព័ន្ធដោយស្វ័យប្រវត្តិ</strong>។</li>
      </ol>
    </div>

    <div class="status-poll">
      <div class="spinner"></div>
      <span id="pollText">កំពុងរង់ចាំ Server ឆ្លើយតប (Auto-connecting)...</span>
    </div>

    <button onclick="checkNow()" class="btn">
      <span>🔁</span>
      <span>ព្យាយាមម្តងទៀតឥឡូវនេះ (Retry)</span>
    </button>
  </div>

  <script>
    async function checkServer() {
      try {
        const res = await fetch('/manifest.json?t=' + Date.now(), { cache: 'no-store' });
        if (res.ok) {
          document.getElementById('pollText').textContent = '✅ Server ដំណើរការហើយ! កំពុងបើកប្រព័ន្ធ...';
          setTimeout(() => {
            window.location.reload();
          }, 400);
          return true;
        }
      } catch (err) {}
      return false;
    }

    async function checkNow() {
      document.getElementById('pollText').textContent = 'កំពុងពិនិត្យ Server...';
      const ok = await checkServer();
      if (!ok) {
        setTimeout(() => {
          document.getElementById('pollText').textContent = '⚠️ Server នៅមិនទាន់បើកដំណើរការឡើយ...';
        }, 500);
      }
    }

    // Auto-poll every 2 seconds
    setInterval(checkServer, 2000);
  </script>
</body>
</html>`;

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('Pre-caching assets skipped during dev:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Network-first strategy with robust cache fallback & offline screen
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  if (url.origin !== location.origin) return;

  // For page navigations (HTML pages)
  const isNavigate = event.request.mode === 'navigate' ||
                     (event.request.headers.get('accept') && event.request.headers.get('accept').includes('text/html'));

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Cache static assets dynamically
        if (response && response.status === 200 && url.pathname.startsWith('/static/')) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return response;
      })
      .catch(async () => {
        // Try local cache match first
        const cachedResponse = await caches.match(event.request);
        if (cachedResponse) {
          return cachedResponse;
        }

        // If navigation request failed and not in cache, return helpful offline UI
        if (isNavigate) {
          return new Response(OFFLINE_HTML, {
            headers: {
              'Content-Type': 'text/html; charset=utf-8',
              'Cache-Control': 'no-store'
            }
          });
        }

        return new Response('', { status: 503, statusText: 'Service Unavailable' });
      })
  );
});
