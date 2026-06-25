<script setup lang="ts">
import { Check, X, Wrench } from 'lucide-vue-next'
import type { ToolCallRequest } from '@/types/domain'

const props = defineProps<{
  toolCalls: ToolCallRequest[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'decide', decisions: Array<{ type: 'approve' | 'reject' }>): void
}>()

function fmtArgs(args: string | Record<string, any> | undefined): string {
  if (!args) return ''
  if (typeof args === 'string') return args
  try {
    return JSON.stringify(args, null, 2)
  } catch {
    return String(args)
  }
}

function approveAll() {
  emit(
    'decide',
    props.toolCalls.map(() => ({ type: 'approve' as const }))
  )
}

function rejectAll() {
  emit(
    'decide',
    props.toolCalls.map(() => ({ type: 'reject' as const }))
  )
}
</script>

<template>
  <div
    class="mt-3 rounded-xl border-2 border-warning/40 bg-warning/5 overflow-hidden"
  >
    <div class="px-4 py-2.5 flex items-center gap-2 border-b border-warning/20">
      <Wrench class="size-4 text-warning shrink-0" />
      <span class="text-sm font-medium text-ink">工具调用需要你的批准</span>
      <span class="text-xs text-ink-subtle ml-auto">{{ toolCalls.length }} 项</span>
    </div>

    <div class="divide-y divide-warning/20">
      <div v-for="(tc, i) in toolCalls" :key="i" class="px-4 py-2.5">
        <div class="flex items-baseline gap-2">
          <code
            class="text-xs font-mono text-accent bg-accent/10 px-1.5 py-0.5 rounded"
          >{{ tc.name }}</code>
          <span v-if="tc.description" class="text-xs text-ink-subtle">{{ tc.description }}</span>
        </div>
        <pre
          v-if="fmtArgs(tc.args)"
          class="mt-1.5 text-xs font-mono text-ink-muted bg-surface-muted rounded p-2 overflow-x-auto max-h-40 whitespace-pre-wrap break-all"
        >{{ fmtArgs(tc.args) }}</pre>
      </div>
    </div>

    <div class="px-4 py-2.5 flex items-center gap-2 bg-warning/5 border-t border-warning/20">
      <button
        class="btn-outline text-xs px-3 py-1.5"
        :disabled="disabled"
        @click="rejectAll"
      >
        <X class="size-3.5" /> 全部拒绝
      </button>
      <button
        class="btn-primary text-xs px-3 py-1.5 ml-auto"
        :disabled="disabled"
        @click="approveAll"
      >
        <Check class="size-3.5" /> 全部批准
      </button>
    </div>
  </div>
</template>
