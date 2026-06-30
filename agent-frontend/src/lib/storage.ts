/**
 * StorageAdapter —— 统一的键值持久化抽象层。
 *
 * 项目硬约束：
 *   - Tauri 桌面/移动端 → @tauri-apps/plugin-store
 *   - Web 端            → IndexedDB（通过 idb）
 *
 * 通过同步检测 window.__TAURI_INTERNALS__ 选择后端，避免与 usePlatform
 * 的异步 detect 产生时序耦合。后端实例懒加载并缓存。
 */
import { openDB, type IDBPDatabase } from 'idb'

export interface StorageAdapter {
  get<T>(key: string): Promise<T | null>
  set<T>(key: string, value: T): Promise<void>
  remove(key: string): Promise<void>
}

const DB_NAME = 'agent-frontend'
const DB_VERSION = 1
const STORE_NAME = 'kv'

let idbPromise: Promise<IDBPDatabase> | null = null

function getIdb(): Promise<IDBPDatabase> {
  if (!idbPromise) {
    idbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME)
        }
      }
    })
  }
  return idbPromise
}

// Tauri LazyStore 懒加载（类型宽松，避免在 web 构建时强依赖 plugin-store 类型）
// 与 @tauri-apps/plugin-store 的 LazyStore 实际签名对齐：
//   set→Promise<void>、get→Promise<T|undefined>、delete→Promise<boolean>、save→Promise<void>
type TauriLazyStore = {
  get<T>(key: string): Promise<T | undefined>
  set(key: string, value: unknown): Promise<void>
  delete(key: string): Promise<boolean>
  save(): Promise<void>
}

let tauriStorePromise: Promise<TauriLazyStore> | null = null

async function getTauriStore(): Promise<TauriLazyStore> {
  if (!tauriStorePromise) {
    tauriStorePromise = (async () => {
      const mod = await import('@tauri-apps/plugin-store')
      const Store = (mod as { LazyStore?: new (path: string) => TauriLazyStore }).LazyStore
        ?? (mod as unknown as { default: new (path: string) => TauriLazyStore }).default
      return new Store('app-settings.json')
    })()
  }
  return tauriStorePromise
}

/** 同步检测 Tauri 环境（__TAURI_INTERNALS__ 在 WebView 加载脚本时即存在）。 */
function isTauriEnv(): boolean {
  return (
    typeof window !== 'undefined' &&
    // @ts-expect-error: Tauri 注入字段在 web 端不存在
    (typeof window.__TAURI_INTERNALS__ !== 'undefined' ||
      // @ts-expect-error: 兼容旧版注入
      typeof window.__TAURI__ !== 'undefined')
  )
}

function createIdbAdapter(): StorageAdapter {
  return {
    async get<T>(key: string): Promise<T | null> {
      try {
        const db = await getIdb()
        const v = await db.get(STORE_NAME, key)
        return (v ?? null) as T | null
      } catch {
        return null
      }
    },
    async set<T>(key: string, value: T): Promise<void> {
      try {
        const db = await getIdb()
        await db.put(STORE_NAME, value, key)
      } catch {
        /* 容量/隐私模式忽略 */
      }
    },
    async remove(key: string): Promise<void> {
      try {
        const db = await getIdb()
        await db.delete(STORE_NAME, key)
      } catch {
        /* ignore */
      }
    }
  }
}

function createTauriAdapter(): StorageAdapter {
  return {
    async get<T>(key: string): Promise<T | null> {
      try {
        const store = await getTauriStore()
        const v = await store.get<T>(key)
        return (v ?? null) as T | null
      } catch {
        return null
      }
    },
    async set<T>(key: string, value: T): Promise<void> {
      try {
        const store = await getTauriStore()
        await store.set(key, value)
        await store.save()
      } catch {
        /* ignore */
      }
    },
    async remove(key: string): Promise<void> {
      try {
        const store = await getTauriStore()
        await store.delete(key)
        await store.save()
      } catch {
        /* ignore */
      }
    }
  }
}

let cachedAdapter: StorageAdapter | null = null

/** 获取当前环境下的存储适配器（单例，首次调用后缓存）。 */
export function getStorage(): StorageAdapter {
  if (!cachedAdapter) {
    cachedAdapter = isTauriEnv() ? createTauriAdapter() : createIdbAdapter()
  }
  return cachedAdapter
}

/** 仅供测试重置单例。 */
export function _resetStorageAdapterForTest(): void {
  cachedAdapter = null
  idbPromise = null
  tauriStorePromise = null
}
