/**
 * useTheme — manages light/dark theme persistence.
 * Storage backend auto-selects: Tauri Store plugin on mobile/desktop,
 * localStorage on the web build.
 */
import { ref, watch } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'agent-frontend:theme'
const mode = ref<ThemeMode>('system')
const resolved = ref<'light' | 'dark'>('light')

let mediaQuery: MediaQueryList | null = null

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

function persist(value: ThemeMode) {
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch {
    /* ignore quota / private mode */
  }
}

function load(): ThemeMode {
  try {
    const v = localStorage.getItem(STORAGE_KEY) as ThemeMode | null
    if (v === 'light' || v === 'dark' || v === 'system') return v
  } catch {
    /* ignore */
  }
  return 'system'
}

export function useTheme() {
  function setMode(next: ThemeMode) {
    mode.value = next
    persist(next)
  }

  function applyInitial() {
    if (typeof window === 'undefined') return
    mode.value = load()
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => {
      const target = mode.value === 'system' ? detectSystem() : mode.value
      applyResolved(target)
    }
    update()
    mediaQuery.addEventListener('change', update)
    watch(mode, update)
  }

  function toggle() {
    const next: ThemeMode = resolved.value === 'dark' ? 'light' : 'dark'
    setMode(next)
  }

  return { mode, resolved, setMode, toggle, applyInitial }
}
