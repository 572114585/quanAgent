<script setup lang="ts">
import { ref, nextTick } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import { Sun, Moon, Monitor } from 'lucide-vue-next'
import { useTheme } from '@/composables/useTheme'

const { mode, setMode } = useTheme()

const options = [
  { value: 'light', label: '浅色', icon: Sun },
  { value: 'dark', label: '深色', icon: Moon },
  { value: 'system', label: '跟随系统', icon: Monitor }
] as const

const buttons = ref<(HTMLButtonElement | null)[]>([])

function setButtonRef(el: Element | ComponentPublicInstance | null, index: number): void {
  buttons.value[index] = el instanceof HTMLButtonElement ? el : null
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
  e.preventDefault()
  const currentIndex = options.findIndex(o => o.value === mode.value)
  if (currentIndex === -1) return
  const direction = e.key === 'ArrowRight' ? 1 : -1
  const nextIndex = (currentIndex + direction + options.length) % options.length
  setMode(options[nextIndex].value)
  void nextTick(() => {
    buttons.value[nextIndex]?.focus()
  })
}
</script>

<template>
  <div
    class="inline-flex items-center bg-surface-muted rounded-lg p-0.5 border border-border"
    role="radiogroup"
    aria-label="主题"
  >
    <button
      v-for="(opt, index) in options"
      :key="opt.value"
      :ref="(el) => setButtonRef(el, index)"
      :class="[
        'p-1.5 rounded-md text-xs transition-colors',
        mode === opt.value ? 'bg-surface text-ink shadow-sm' : 'text-ink-subtle hover:text-ink'
      ]"
      :aria-label="opt.label"
      :aria-checked="mode === opt.value"
      :tabindex="mode === opt.value ? 0 : -1"
      role="radio"
      @click="setMode(opt.value)"
      @keydown="onKeydown"
    >
      <component :is="opt.icon" class="size-3.5" aria-hidden="true" />
    </button>
  </div>
</template>
