import {useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction} from 'react';

const prefix = 'local-ai-draft-v1:';
function failed() { window.dispatchEvent(new Event('draft-save-failed')); }

// Keep drafts separate from service configuration, credentials and job state.
export function readDraft<T>(key: string, fallback: T, valid?: (value:unknown)=>boolean): T {
  try {
    const raw = localStorage.getItem(prefix + key);
    if (raw === null) return fallback;
    const value = JSON.parse(raw);
    if (valid) return valid(value) ? value : fallback;
    if (fallback === null) return value;
    if (typeof value !== typeof fallback || value === null || Array.isArray(value) !== Array.isArray(fallback)) return fallback;
    if (typeof fallback === 'object') return {...fallback, ...value};
    return value;
  } catch { return fallback; }
}

export function useDraft<T>(key: string, fallback: T, valid?: (value:unknown)=>boolean): [T, Dispatch<SetStateAction<T>>] {
  const [value, update] = useState<T>(() => readDraft(key, fallback, valid));
  const current = useRef(value);
  const set = useCallback<Dispatch<SetStateAction<T>>>((next) => {
    const resolved = typeof next === 'function' ? (next as (old:T)=>T)(current.current) : next;
    current.current = resolved;
    try { localStorage.setItem(prefix + key, JSON.stringify(resolved)); } catch { failed(); }
    update(resolved);
  }, [key]);
  return [value, set];
}

let database: Promise<IDBDatabase> | undefined;
function fileDatabase() {
  return database ??= new Promise((resolve, reject) => {
    const request = indexedDB.open('local-ai-draft-files', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('files');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => { database = undefined; reject(request.error); };
  });
}

// IndexedDB stores File blobs without converting large audio/video files to JSON.
export function useDraftFile(key: string): [File|null, (file:File|null)=>void] {
  const [file, update] = useState<File|null>(null);
  const changed = useRef(false);
  const queue = useRef(Promise.resolve());
  useEffect(() => {
    let cancelled = false;
    fileDatabase().then(db => new Promise<File|null>((resolve,reject) => {
      const request = db.transaction('files').objectStore('files').get(key);
      request.onsuccess = () => resolve(request.result instanceof File ? request.result : null);
      request.onerror = () => reject(request.error);
    })).then(value => { if (!cancelled && !changed.current) update(value); }).catch(failed);
    return () => { cancelled = true; };
  }, [key]);
  const set = useCallback((value:File|null) => {
    changed.current = true;
    update(value);
    queue.current = queue.current.then(async () => {
      const db = await fileDatabase();
      await new Promise<void>((resolve,reject) => {
        const transaction = db.transaction('files','readwrite');
        const store = transaction.objectStore('files');
        if (value) store.put(value,key); else store.delete(key);
        transaction.oncomplete = () => resolve();
        transaction.onabort = () => reject(transaction.error);
        transaction.onerror = () => reject(transaction.error);
      });
    }).catch(failed);
  }, [key]);
  return [file,set];
}
