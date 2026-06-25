<script setup lang="ts">
import { useSettingsStore } from '@/stores/settings'
import { setRuntimeBaseUrl } from '@/api/sse'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'

const settings = useSettingsStore()

function applyApiBase() {
  setRuntimeBaseUrl(settings.apiBaseUrl)
}

import { onMounted } from 'vue'
onMounted(applyApiBase)
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
            <p class="text-xs text-ink-subtle mt-0.5">切换浅色、深色或跟随系统。</p>
          </div>
          <ThemeToggle />
        </div>
      </section>

      <section class="space-y-3">
        <h2 class="text-sm font-medium text-ink">后端</h2>
        <div class="rounded-xl border border-border p-4 space-y-3">
          <div>
            <label class="block text-xs text-ink-subtle mb-1">API Base URL</label>
            <input
              v-model="settings.apiBaseUrl"
              class="input-base"
              placeholder="http://localhost:8000"
              @change="applyApiBase"
              @blur="applyApiBase"
            />
            <p class="text-xs text-ink-subtle mt-1">
              指向 <code>run.py</code> 启动的 FastAPI 服务。改完立即生效。
            </p>
          </div>
          <div>
            <label class="block text-xs text-ink-subtle mb-1">Model</label>
            <input
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
