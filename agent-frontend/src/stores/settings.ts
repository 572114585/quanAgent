/**
 * Settings store — user preferences persisted to localStorage / Tauri Store.
 */
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { setRuntimeBaseUrl } from '@/api/sse'

const STORAGE_KEY = 'agent-frontend:settings'

interface Settings {
  apiBaseUrl: string
  model: string
  streamEnabled: boolean
}

const defaults: Settings = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '',
  model: 'agent-default',
  streamEnabled: true
}

function load(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...defaults, ...JSON.parse(raw) }
  } catch {
    /* ignore */
  }
  return { ...defaults }
}

export const useSettingsStore = defineStore('settings', () => {
  const initial = load()
  const apiBaseUrl = ref(initial.apiBaseUrl)
  const model = ref(initial.model)
  const streamEnabled = ref(initial.streamEnabled)

  watch(apiBaseUrl, (newUrl) => {
    setRuntimeBaseUrl(newUrl)
  }, { immediate: false })

  watch(
    [apiBaseUrl, model, streamEnabled],
    () => {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            apiBaseUrl: apiBaseUrl.value,
            model: model.value,
            streamEnabled: streamEnabled.value
          })
        )
      } catch {
        /* ignore */
      }
    },
    { deep: true }
  )

  return { apiBaseUrl, model, streamEnabled }
})
