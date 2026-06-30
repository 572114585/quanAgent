/**
 * Settings store — 用户偏好，持久化到 StorageAdapter。
 *
 * 项目硬约束：
 *   - 持久化后端由 getStorage() 自动选择（Tauri→plugin-store / Web→IndexedDB）
 *   - API Base URL 配置优先于环境变量（watch immediate + load 时显式应用，修复原 S3 bug）
 *
 * schema 版本：通过 version 字段标记，未来字段变更在 migrate() 中按版本号升级。
 */
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { setRuntimeBaseUrl } from '@/api/sse'
import { getStorage } from '@/lib/storage'

const STORAGE_KEY = 'settings'
const CURRENT_VERSION = 1

/** 与 vite.config.ts proxy target 对齐的默认值，供 SettingsView 重置。 */
export const DEFAULT_API_BASE_URL = 'http://localhost:8000'

interface Settings {
  version: number
  apiBaseUrl: string
  model: string
  streamEnabled: boolean
}

const defaultSettings: Settings = {
  version: CURRENT_VERSION,
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '',
  model: 'agent-default',
  streamEnabled: true
}

/** 类型守卫：校验从存储反序列化出的数据结构。 */
function isSettings(v: unknown): v is Settings {
  if (typeof v !== 'object' || v === null) return false
  const o = v as Record<string, unknown>
  return (
    typeof o.apiBaseUrl === 'string' &&
    typeof o.model === 'string' &&
    typeof o.streamEnabled === 'boolean'
  )
}

/** schema 迁移：按版本号升级旧数据，未知/损坏数据回退默认。 */
function migrate(raw: unknown): Settings {
  if (!isSettings(raw)) return { ...defaultSettings }
  // 未来版本迁移示例：
  // if (raw.version < 2) { raw = { ...raw, newField: defaultValue } }
  return { ...defaultSettings, ...raw, version: CURRENT_VERSION }
}

export const useSettingsStore = defineStore('settings', () => {
  const storage = getStorage()

  const apiBaseUrl = ref(defaultSettings.apiBaseUrl)
  const model = ref(defaultSettings.model)
  const streamEnabled = ref(defaultSettings.streamEnabled)
  const loaded = ref(false)

  let saveTimer: ReturnType<typeof setTimeout> | null = null

  /** debounce 持久化，避免输入逐字符写盘。load 完成前不写盘。 */
  function scheduleSave() {
    if (!loaded.value) return
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(() => {
      void storage.set(STORAGE_KEY, {
        version: CURRENT_VERSION,
        apiBaseUrl: apiBaseUrl.value,
        model: model.value,
        streamEnabled: streamEnabled.value
      })
    }, 300)
  }

  async function load() {
    try {
      const raw = await storage.get<unknown>(STORAGE_KEY)
      const s = migrate(raw)
      apiBaseUrl.value = s.apiBaseUrl
      model.value = s.model
      streamEnabled.value = s.streamEnabled
      // 关键：启动时把持久化的 apiBaseUrl 应用到 runtimeBaseUrl
      // 原 watch immediate:false 导致此处被跳过，违反"配置 > 环境变量"约束
      setRuntimeBaseUrl(s.apiBaseUrl)
    } catch {
      /* 存储异常时用默认值 */
    } finally {
      loaded.value = true
    }
  }

  // apiBaseUrl 变化时同步 runtimeBaseUrl 并持久化
  watch(apiBaseUrl, (newUrl) => {
    setRuntimeBaseUrl(newUrl)
    scheduleSave()
  })

  // model / streamEnabled 变化时持久化
  watch([model, streamEnabled], scheduleSave)

  return { apiBaseUrl, model, streamEnabled, loaded, load }
})
