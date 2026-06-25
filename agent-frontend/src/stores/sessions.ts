/**
 * Sessions store — owns the list of conversations, active selection,
 * and CRUD operations. Persistence is added in Phase 4.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Session } from '@/types/domain'

function uid() {
  return 's_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
}

export const useSessionsStore = defineStore('sessions', () => {
  const list = ref<Session[]>([])
  const activeId = ref<string | null>(null)

  const active = computed(() => list.value.find((s) => s.id === activeId.value) ?? null)

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
    return session
  }

  function activate(id: string) {
    if (list.value.some((s) => s.id === id)) {
      activeId.value = id
    }
  }

  function remove(id: string) {
    list.value = list.value.filter((s) => s.id !== id)
    if (activeId.value === id) activeId.value = list.value[0]?.id ?? null
  }

  function rename(id: string, title: string) {
    const s = list.value.find((x) => x.id === id)
    if (!s) return
    const trimmed = title.trim() || '新对话'
    s.title = trimmed
    s.updatedAt = Date.now()
  }

  function touch(id: string, patch: Partial<Session> = {}) {
    const s = list.value.find((x) => x.id === id)
    if (!s) return
    Object.assign(s, patch, { updatedAt: Date.now() })
  }

  function load() {
    // Phase 4 will hydrate from IndexedDB / Tauri Store.
  }

  return { list, activeId, active, create, activate, remove, rename, touch, load }
})
