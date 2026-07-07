/**
 * Sessions store — 会话列表、当前选中、CRUD。
 *
 * 持久化到 StorageAdapter（Tauri→plugin-store / Web→IndexedDB）。
 * isLoaded 标志供路由守卫等待加载完成，避免组件读到空列表闪烁。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Session } from '@/types/domain'
import { getStorage } from '@/lib/storage'
import { fetchSessions } from '@/api/chat'

const STORAGE_KEY = 'sessions'

/** 允许更新的字段，排除不可变字段 id / createdAt。 */
export type SessionPatch = Partial<Omit<Session, 'id' | 'createdAt'>>

function uid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return 's_' + crypto.randomUUID()
  }
  return 's_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
}

export const useSessionsStore = defineStore('sessions', () => {
  const storage = getStorage()
  const list = ref<Session[]>([])
  const activeId = ref<string | null>(null)
  const isLoaded = ref(false)

  const active = computed(() => list.value.find((s) => s.id === activeId.value) ?? null)

  function isSession(v: unknown): v is Session {
    if (typeof v !== 'object' || v === null) return false
    const o = v as Record<string, unknown>
    return (
      typeof o.id === 'string' &&
      typeof o.title === 'string' &&
      typeof o.createdAt === 'number' &&
      typeof o.updatedAt === 'number' &&
      typeof o.messageCount === 'number'
    )
  }

  let saveTimer: ReturnType<typeof setTimeout> | null = null

  interface PersistedState {
    list: Session[]
    activeId: string | null
  }

  function isPersistedState(v: unknown): v is PersistedState {
    if (typeof v !== 'object' || v === null) return false
    const o = v as Record<string, unknown>
    return Array.isArray(o.list) && o.list.every(isSession) && (o.activeId === null || typeof o.activeId === 'string')
  }

  /** debounce 持久化，load 完成前不写盘。 */
  function scheduleSave() {
    if (!isLoaded.value) return
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(() => {
      void storage.set(STORAGE_KEY, {
        list: list.value,
        activeId: activeId.value
      } satisfies PersistedState)
    }, 300)
  }

  async function load() {
    try {
      const raw = await storage.get<unknown>(STORAGE_KEY)
      if (isPersistedState(raw)) {
        list.value = raw.list
        if (raw.activeId && raw.list.some((s) => s.id === raw.activeId)) {
          activeId.value = raw.activeId
        }
      } else if (Array.isArray(raw) && raw.every(isSession)) {
        list.value = raw
      }
    } catch {
      /* ignore local storage errors */
    }

    try {
      const backendSessions = await fetchSessions()
      if (backendSessions.length > 0) {
        // 合并语义：后端 updatedAt 比 local 新 → 同步 updatedAt / messageCount
        // 不覆盖 title（用户可能正在编辑）和 activeId 等本地状态
        const byId = new Map(list.value.map((s) => [s.id, s]))
        for (const bs of backendSessions) {
          const local = byId.get(bs.id)
          if (!local) {
            list.value.push(bs)
          } else if (bs.updatedAt > local.updatedAt) {
            local.updatedAt = bs.updatedAt
            local.messageCount = bs.messageCount
          }
        }
        list.value.sort((a, b) => b.updatedAt - a.updatedAt)
      }
    } catch {
      /* ignore backend sync errors */
    } finally {
      isLoaded.value = true
      scheduleSave()
    }
  }

  function create(): Session {
    const now = Date.now()
    const session: Session = {
      id: uid(),
      title: '新对话',
      createdAt: now,
      updatedAt: now,
      messageCount: 0
    }
    list.value.unshift(session)
    activeId.value = session.id
    scheduleSave()
    return session
  }

  function activate(id: string) {
    if (list.value.some((s) => s.id === id)) {
      activeId.value = id
      scheduleSave()
    }
  }

  function remove(id: string) {
    const idx = list.value.findIndex((s) => s.id === id)
    list.value = list.value.filter((s) => s.id !== id)
    if (activeId.value === id) {
      // 回退到相邻兄弟而非列表头部，更符合用户预期
      const next = list.value[idx] ?? list.value[idx - 1] ?? null
      activeId.value = next?.id ?? null
    }
    scheduleSave()
  }

  function rename(id: string, title: string) {
    const s = list.value.find((x) => x.id === id)
    if (!s) return
    const trimmed = title.trim() || '新对话'
    if (s.title === trimmed) return
    s.title = trimmed
    s.updatedAt = Date.now()
    scheduleSave()
  }

  function touch(id: string, patch: SessionPatch = {}) {
    const s = list.value.find((x) => x.id === id)
    if (!s) return
    Object.assign(s, patch, { updatedAt: Date.now() })
    scheduleSave()
  }

  return { list, activeId, active, isLoaded, create, activate, remove, rename, touch, load }
})
