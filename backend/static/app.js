/**
 * CarbonPilot Frontend Offline-First Logic (Donut Challenge)
 * Handles IndexedDB queueing, simulated disconnects, idempotency, and background sync.
 */

const API_BASE = window.location.origin;
let simulatedOffline = false;

// Register Service Worker if supported
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js')
    .then((reg) => console.log('[Client] Service Worker registered with scope:', reg.scope))
    .catch((err) => console.warn('[Client] Service Worker registration failed:', err));
}

// Detect connectivity (incorporates simulated offline switch)
function isOnline() {
  return navigator.onLine && !simulatedOffline;
}

function setSimulatedOffline(isOffline) {
  simulatedOffline = isOffline;
  console.log(`[Client] Network mode set to: ${simulatedOffline ? 'SIMULATED OFFLINE 🔴' : 'ONLINE 🟢'}`);
  updateConnectionUI();
}

// Open IndexedDB instance
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

// Queue workflow in IndexedDB for subsequent background sync
async function queueWorkflow(payload) {
  const db = await openDB();
  const tx = db.transaction('outbox', 'readwrite');
  const store = tx.objectStore('outbox');

  // Ensure an idempotency key exists
  const workflowId = payload.workflow_id || `wf_offline_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
  const enrichedPayload = {
    ...payload,
    workflow_id: workflowId,
    is_offline: true,
  };

  const request = {
    workflow_id: workflowId,
    url: `${API_BASE}/workflows`,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(enrichedPayload),
    payload: enrichedPayload,
    timestamp: Date.now(),
  };

  await store.add(request);
  console.log('[Client] Workflow queued in IndexedDB outbox:', workflowId);

  // Request Background Sync from Service Worker if available
  if ('serviceWorker' in navigator && 'SyncManager' in window) {
    try {
      const registration = await navigator.serviceWorker.ready;
      await registration.sync.register('workflow-sync');
      console.log('[Client] Background sync registered for workflow-sync');
    } catch (err) {
      console.warn('[Client] Background sync registration skipped:', err);
    }
  }

  await refreshQueueCount();
  return { status: 'queued_offline', workflow_id: workflowId, message: 'Saved to offline outbox' };
}

// Submit workflow (Online or Offline with automatic fallback)
async function submitWorkflow(payload) {
  if (isOnline()) {
    try {
      const response = await fetch(`${API_BASE}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.warn('[Client] Direct submission failed. Falling back to offline queue:', error);
      const queued = await queueWorkflow(payload);
      return { ...queued, message: 'Network failed, saved to IndexedDB outbox for sync' };
    }
  } else {
    console.log('[Client] Device is offline. Queueing directly in IndexedDB.');
    return await queueWorkflow(payload);
  }
}

// Manually process all queued requests in IndexedDB outbox
async function syncOutboxManually() {
  const db = await openDB();
  const tx = db.transaction('outbox', 'readonly');
  const store = tx.objectStore('outbox');
  const allRequests = await new Promise((res, rej) => {
    const req = store.getAll();
    req.onsuccess = () => res(req.result);
    req.onerror = () => rej(req.error);
  });

  if (!allRequests || allRequests.length === 0) {
    console.log('[Client] IndexedDB outbox is empty. Triggering server-side sync.');
    await fetch(`${API_BASE}/sync`, { method: 'POST' });
    return { synced: 0, message: 'Outbox is empty' };
  }

  let syncedCount = 0;
  for (const req of allRequests) {
    try {
      const res = await fetch(req.url, {
        method: req.method,
        headers: req.headers,
        body: req.body,
      });
      if (res.ok) {
        const delTx = db.transaction('outbox', 'readwrite');
        await delTx.objectStore('outbox').delete(req.id);
        syncedCount++;
      }
    } catch (e) {
      console.error('[Client] Failed to push request ID:', req.id, e);
    }
  }

  // Also trigger server-side sync for processing pending items in SQLite
  try {
    await fetch(`${API_BASE}/sync`, { method: 'POST' });
  } catch (e) {
    console.warn('[Client] Server-side sync trigger notification failed:', e);
  }

  await refreshQueueCount();
  return { synced: syncedCount, total: allRequests.length };
}

// Helper to count pending IndexedDB outbox records
async function getOutboxCount() {
  try {
    const db = await openDB();
    const tx = db.transaction('outbox', 'readonly');
    const store = tx.objectStore('outbox');
    return await new Promise((res, rej) => {
      const req = store.count();
      req.onsuccess = () => res(req.result);
      req.onerror = () => rej(req.error);
    });
  } catch (e) {
    return 0;
  }
}

async function refreshQueueCount() {
  const count = await getOutboxCount();
  const badge = document.getElementById('offline-queue-count');
  if (badge) {
    badge.textContent = count;
    badge.className = count > 0 
      ? 'px-2 py-0.5 text-xs font-bold rounded-full bg-amber-500 text-black' 
      : 'px-2 py-0.5 text-xs font-bold rounded-full bg-slate-700 text-slate-300';
  }
}

function updateConnectionUI() {
  const isUp = isOnline();
  const badge = document.getElementById('network-state-badge');
  const dot = document.getElementById('network-state-dot');
  const text = document.getElementById('network-state-text');

  if (dot && text) {
    if (isUp) {
      dot.className = 'w-2.5 h-2.5 rounded-full bg-green-400 inline-block animate-pulse';
      text.textContent = 'ONLINE';
      if (badge) badge.className = 'flex items-center gap-2 bg-emerald-950/80 border border-emerald-700/50 px-3 py-1.5 rounded-full text-xs font-semibold text-emerald-300';
    } else {
      dot.className = 'w-2.5 h-2.5 rounded-full bg-red-400 inline-block';
      text.textContent = simulatedOffline ? 'OFFLINE (Simulated)' : 'OFFLINE';
      if (badge) badge.className = 'flex items-center gap-2 bg-red-950/80 border border-red-700/50 px-3 py-1.5 rounded-full text-xs font-semibold text-red-300';
    }
  }
}

// Listen for network connectivity transitions
window.addEventListener('online', async () => {
  console.log('🟢 Back online! Auto-triggering sync...');
  updateConnectionUI();
  await syncOutboxManually();
});

window.addEventListener('offline', () => {
  console.log('🔴 Offline mode detected');
  updateConnectionUI();
});

document.addEventListener('DOMContentLoaded', () => {
  updateConnectionUI();
  refreshQueueCount();
});
