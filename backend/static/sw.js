// Service Worker for CarbonPilot - Donut Challenge (Intermittent Connectivity)
const OFFLINE_QUEUE = 'offline-queue';

self.addEventListener('install', (event) => {
  console.log('[SW] Installing Service Worker...');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Service Worker Activated.');
  event.waitUntil(self.clients.claim());
});

// Background Sync listener
self.addEventListener('sync', (event) => {
  console.log('[SW] Background sync event triggered:', event.tag);
  if (event.tag === 'workflow-sync') {
    event.waitUntil(syncWorkflows());
  }
});

async function syncWorkflows() {
  console.log('[SW] Initiating outbox sync from IndexedDB...');
  const db = await openDB();
  const tx = db.transaction('outbox', 'readwrite');
  const store = tx.objectStore('outbox');
  const allRequests = await store.getAll();

  for (const request of allRequests) {
    try {
      console.log('[SW] Attempting to sync request ID:', request.id, request.url);
      const response = await fetch(request.url, {
        method: request.method,
        headers: request.headers,
        body: request.body,
      });

      if (response.ok) {
        console.log('[SW] Successfully synced request ID:', request.id);
        const delTx = db.transaction('outbox', 'readwrite');
        await delTx.objectStore('outbox').delete(request.id);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      console.error('[SW] Sync failed for request ID:', request.id, 'will retry:', error);
      throw error;  // Browser will retry with exponential backoff
    }
  }
}

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('workflow-queue', 1);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('outbox')) {
        db.createObjectStore('outbox', { keyPath: 'id', autoIncrement: true });
      }
    };
  });
}
