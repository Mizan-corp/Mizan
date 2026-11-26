/**
 * Offline sale queue — IndexedDB-backed.
 *
 * When a checkout cannot reach the server (network error, not a business
 * rejection), the sale payload is queued locally. On reconnect the queue is
 * replayed; HTTP failures with a body (4xx/5xx) are conflicts surfaced to the
 * cashier for manual resolution — they are NOT retried blindly.
 *
 * Every sale carries `local_id`, a UUID made on the device before the first attempt and kept
 * across retries and the queue: the server records a sale sent twice with the same local_id once
 * (SAL-2), so replaying after a lost answer never sells twice.
 */
const DB_NAME = "mizan";
const STORE = "sale_queue";

export type QueueStatus = "waiting" | "syncing" | "synced" | "conflict";

export interface QueuedSale {
  id: string;
  payload: unknown;
  savedAt: string;
  status: QueueStatus;
  error?: string;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest): Promise<T> {
  const db = await open();
  return new Promise<T>((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const req = fn(t.objectStore(STORE));
    req.onsuccess = () => resolve(req.result as T);
    req.onerror = () => reject(req.error);
    t.oncomplete = () => db.close();
  });
}

/** A random UUID (v4) for a sale's local_id; also where crypto.randomUUID is missing (plain HTTP). */
export function newLocalId(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  const b = new Uint8Array(16);
  if (c && typeof c.getRandomValues === "function") c.getRandomValues(b);
  else for (let i = 0; i < 16; i++) b[i] = Math.floor(Math.random() * 256);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** The payload with a local_id (its own if it has one: the key must stay the same). */
export function withLocalId<T>(payload: T): T & { local_id: string } {
  const p = (payload ?? {}) as T & { local_id?: string };
  return { ...p, local_id: p.local_id || newLocalId() };
}

export async function enqueueSale(payload: unknown): Promise<QueuedSale> {
  const sale: QueuedSale = {
    id: `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    payload: withLocalId(payload),
    savedAt: new Date().toISOString(),
    status: "waiting",
  };
  await tx("readwrite", (s) => s.add(sale));
  return sale;
}

export async function listQueue(): Promise<QueuedSale[]> {
  const all = await tx<QueuedSale[]>("readonly", (s) => s.getAll());
  return (all ?? []).sort((a, b) => a.savedAt.localeCompare(b.savedAt));
}

export async function updateSale(sale: QueuedSale): Promise<void> {
  await tx("readwrite", (s) => s.put(sale));
}

export async function removeSale(id: string): Promise<void> {
  await tx("readwrite", (s) => s.delete(id));
}

/** Replay the waiting entries against the API. Returns per-sale results. */
export async function replayQueue(
  post: (payload: unknown) => Promise<unknown>,
): Promise<{ synced: number; conflicts: QueuedSale[] }> {
  // "syncing" left over from a closed tab is retried too: the local_id makes a repeat harmless.
  const waiting = (await listQueue()).filter((s) => s.status === "waiting" || s.status === "syncing");
  let synced = 0;
  const conflicts: QueuedSale[] = [];
  for (const sale of waiting) {
    sale.status = "syncing";
    sale.payload = withLocalId(sale.payload); // entries queued before local_id existed get one, kept from now on
    await updateSale(sale);
    try {
      await post(sale.payload);
      sale.status = "synced";
      synced++;
      await removeSale(sale.id); // synced entries leave the queue entirely
    } catch (err) {
      const msg = err instanceof Error ? err.message : "فشل غير معروف";
      // HTTP-level error (server answered with rejection) → conflict for manual
      // resolution; anything else is a network failure → retry next replay.
      const isHttpError = typeof err === "object" && err !== null && "status" in err;
      sale.status = isHttpError ? "conflict" : "waiting";
      sale.error = msg;
      if (isHttpError) conflicts.push(sale);
    }
    await updateSale(sale);
  }
  return { synced, conflicts };
}
