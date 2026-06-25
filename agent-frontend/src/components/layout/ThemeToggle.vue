<script setup lang="ts">
import { Sun, Moon, Monitor } from 'lucide-vue-next'
import { useTheme, type ThemeMode } from '@/composables/useTheme'

const { mode, setMode } = useTheme()

const options: Array<{ value: ThemeMode; label: string; icon: typeof Sun }> = [
  { value: 'light', label: '浅色', icon: Sun },
  { value: 'dark', label: '深色', icon: Moon },
  { value: 'system', label: '跟随系统', icon: Monitor }
]
</script>

<template>
  <div
    class="inline-flex items-center bg-surface-muted rounded-lg p-0.5 border border-border"
    role="radiogroup"
    aria-label="主题"
  >
    <button
      v-for="opt in options"
      :key="opt.value"
      :class="[
        'p-1.5 rounded-md text-xs transition-colors',
        mode === opt.value ? 'bg-surface text-ink shadow-sm' : 'text-ink-subtle hover:text-ink'
      ]"
      :aria-label="opt.label"
      :aria-checked="mode === opt.value"
      role="radio"
      @click="setMode(opt.value)"
    >
      <component :is="opt.icon" class="size-3.5" />
    </button>
  </div>
</template>
