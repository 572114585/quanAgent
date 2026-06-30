/**
 * useTheme — 明/暗主题管理。
 *
 * 持久化后端由 StorageAdapter 自动选择（Tauri→plugin-store / Web→IndexedDB），
 * 不再直接使用 localStorage，符合项目硬约束。
 *
 * applyInitial 增加防重入守卫，避免多次调用导致 MediaQueryList
 * 监听器与 watch 累积泄漏。
 */
import { ref, watch } from 'vue'
import { getStorage } from '@/lib/storage'

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'theme'
const mode = ref<ThemeMode>('system')
const resolved = ref<'light' | 'dark'>('light')

let mediaQuery: MediaQueryList | null = null
let updateFn: (() => void) | null = null
let initialized = false

function detectSystem(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyResolved(value: 'light' | 'dark') {
  resolved.value = value
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.toggle('dark', value === 'dark')
  root.style.colorScheme = value
}

function isThemeMode(v: unknown): v is ThemeMode {
  return v === 'light' || v === 'dark' || v === 'system'
}

export function useTheme() {
  function setMode(next: ThemeMode) {
    mode.value = next
    void getStorage().set(STORAGE_KEY, next)
  }

  /**
   * 初始化主题：从存储加载、应用 resolved、注册 mediaQuery 监听与 watch。
   * 防重入：多次调用仅首次执行实际逻辑，避免监听器/watch 累积泄漏。
   * 异步：需在 main.ts 中 await 后再 mount 应用，避免 FOUC。
   */
  async function applyInitial() {
    if (initialized || typeof window === 'undefined') return
    initialized = true

    try {
      const stored = await getStorage().get<unknown>(STORAGE_KEY)
      if (isThemeMode(stored)) mode.value = stored
    } catch {
      /* 读取失败保持默认 'system' */
    }

    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    updateFn = () => {
      const target = mode.value === 'system' ? detectSystem() : mode.value
      applyResolved(target)
    }
    updateFn()
    mediaQuery.addEventListener('change', updateFn)
    watch(mode, updateFn)
  }

  function toggle() {
    const next: ThemeMode = resolved.value === 'dark' ? 'light' : 'dark'
    setMode(next)
  }

  return { mode, resolved, setMode, toggle, applyInitial }
}
