<script setup lang="ts">
import { ref, watch, onScopeDispose } from 'vue'
import { useSettingsStore, DEFAULT_API_BASE_URL } from '@/stores/settings'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'
import { Check, RotateCcw } from 'lucide-vue-next'

const settings = useSettingsStore()

/**
 * 本地 draft 暂存输入，避免每次按键都触发 store 持久化写盘。
 * store 层的 watch(immediate:true) 会在值变化时同步 setRuntimeBaseUrl。
 */
const draftUrl = ref(settings.apiBaseUrl || DEFAULT_API_BASE_URL)
const urlError = ref('')
const saved = ref(false)
let savedTimer: ReturnType<typeof setTimeout> | null = null

// store 值被外部修改时同步回 draft
watch(() => settings.apiBaseUrl, (v) => {
  if (v !== draftUrl.value) draftUrl.value = v
})

onScopeDispose(() => {
  if (savedTimer) clearTimeout(savedTimer)
})

/** 校验 URL：仅允许 http/https。返回错误消息或 null。 */
function validateUrl(value: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) return 'URL 不能为空'
  try {
    const u = new URL(trimmed)
    if (u.protocol !== 'http:' && u.protocol !== 'https:') {
      return '仅支持 http/https 协议'
    }
    return null
  } catch {
    return 'URL 格式无效，需包含协议与主机（如 http://localhost:8000）'
  }
}

function flashSaved() {
  saved.value = true
  if (savedTimer) clearTimeout(savedTimer)
  savedTimer = setTimeout(() => {
    saved.value = false
  }, 2000)
}

function saveApiBase() {
  const err = validateUrl(draftUrl.value)
  if (err) {
    urlError.value = err
    return
  }
  urlError.value = ''
  settings.apiBaseUrl = draftUrl.value.trim()
  flashSaved()
}

function resetApiBase() {
  draftUrl.value = DEFAULT_API_BASE_URL
  urlError.value = ''
  settings.apiBaseUrl = DEFAULT_API_BASE_URL
  flashSaved()
}

function clearError() {
  if (urlError.value) urlError.value = ''
}
</script>

<template>
  <div class="h-full overflow-y-auto">
    <div class="max-w-2xl mx-auto px-6 py-8 space-y-8">
      <header>
        <h1 class="text-xl font-semibold text-ink">设置</h1>
        <p class="text-sm text-ink-muted mt-1">个性化你的 Agent 前端体验。</p>
      </header>

      <section class="space-y-3">
        <h2 class="text-sm font-medium text-ink">外观</h2>
        <div class="rounded-xl border border-border p-4 flex items-center justify-between">
          <div>
            <p class="text-sm text-ink">主题</p>
            <p class="text-xs text-ink-muted mt-0.5">切换浅色、深色或跟随系统。</p>
          </div>
          <ThemeToggle />
        </div>
      </section>

      <section class="space-y-3">
        <h2 class="text-sm font-medium text-ink">后端</h2>
        <div class="rounded-xl border border-border p-4 space-y-3">
          <div>
            <label for="api-base-url" class="block text-xs text-ink-muted mb-1">API Base URL</label>
            <div class="flex gap-2">
              <input
                id="api-base-url"
                v-model="draftUrl"
                class="input-base flex-1"
                :class="{ 'border-danger focus:ring-danger/40': urlError }"
                placeholder="http://localhost:8000"
                autocomplete="off"
                spellcheck="false"
                @input="clearError"
                @keydown.enter.prevent="saveApiBase"
              />
              <button
                type="button"
                class="btn-primary shrink-0 flex items-center gap-1.5"
                @click="saveApiBase"
              >
                <Check v-if="saved" class="size-4" />
                <span>{{ saved ? '已保存' : '保存' }}</span>
              </button>
              <button
                type="button"
                class="px-3 py-1.5 text-xs rounded-md text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors shrink-0 flex items-center gap-1"
                aria-label="重置为默认值"
                title="重置为默认值"
                @click="resetApiBase"
              >
                <RotateCcw class="size-3.5" />
                重置
              </button>
            </div>
            <p v-if="urlError" class="text-xs text-danger mt-1" role="alert">{{ urlError }}</p>
            <p v-else class="text-xs text-ink-muted mt-1">
              指向 <code>run.py</code> 启动的 FastAPI 服务。仅支持 http/https 协议。
            </p>
          </div>
          <div>
            <label for="model-input" class="block text-xs text-ink-muted mb-1">Model</label>
            <input
              id="model-input"
              v-model="settings.model"
              class="input-base"
              placeholder="agent-default"
            />
          </div>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="settings.streamEnabled"
              type="checkbox"
              class="size-4 rounded border-border text-accent focus:ring-accent/40"
            />
            <span class="text-sm text-ink">流式输出（SSE）</span>
          </label>
        </div>
      </section>

      <section class="space-y-3">
        <h2 class="text-sm font-medium text-ink">关于</h2>
        <div class="rounded-xl border border-border p-4 text-xs text-ink-muted space-y-1.5">
          <p>Agent Frontend · Vue 3 + Tauri 2</p>
          <p>支持 Web、桌面端 (Win/Mac/Linux) 与移动端 (Android/iOS)。</p>
          <p>后端协议：POST /chat · POST /chat/resume · POST /upload</p>
        </div>
      </section>
    </div>
  </div>
</template>