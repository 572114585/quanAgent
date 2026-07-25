<script setup lang="ts">
import { computed } from 'vue'
import { Check, X, Wrench } from 'lucide-vue-next'
import type { InterruptGroup, ResumeGroup, ToolCallRequest } from '@/types/domain'

const props = defineProps<{
  groups: InterruptGroup[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'decide', groups: ResumeGroup[]): void
}>()

// 跨组平铺的工具调用，UI 仍按一维列表展示（用户不感知 interrupt 分组）
const flatToolCalls = computed<ToolCallRequest[]>(() =>
  props.groups.flatMap((g) => g.toolCalls || [])
)

function fmtArgs(args: string | Record<string, any> | undefined): string {
  if (!args) return ''
  if (typeof args === 'string') return args
  try {
    return JSON.stringify(args, null, 2)
  } catch {
    return String(args)
  }
}

function riskText(tc: ToolCallRequest): string {
  return tc.riskNote || tc.description || ''
}

function emitAll(decisionType: 'approve' | 'reject') {
  emit(
    'decide',
    props.groups.map((g) => ({
      interruptId: g.interruptId,
      kind: 'tool_approval' as const,
      actionHash:
        g.actionHash ||
        g.toolCalls?.[0]?.actionHash ||
        '',
      decisions: (g.toolCalls || []).map(() => ({ type: decisionType }))
    }))
  )
}

function approveAll() {
  emitAll('approve')
}

function rejectAll() {
  emitAll('reject')
}
</script>

<template>
  <div
    class="rounded-xl border border-border bg-surface-elevated/95 backdrop-blur-md overflow-hidden"
  >
    <div class="px-4 py-2.5 flex items-center gap-2 border-b border-border">
      <Wrench class="size-4 text-warning shrink-0" />
      <span class="text-sm font-medium text-ink">工具调用需要你的批准</span>
      <span class="text-xs text-ink-subtle ml-auto">{{ flatToolCalls.length }} 项</span>
    </div>
    <p class="px-4 pt-2 text-xs text-ink-subtle">
      仅批准本次调用。工作区内常规读写与构建会自动执行；此处通常是解释器内联、联网、安装或未知命令。
      硬拒绝（命令替换、越出工作区、灾难性命令）即使批准也无法执行。
    </p>

    <div class="divide-y divide-border">
      <div v-for="(tc, i) in flatToolCalls" :key="i" class="px-4 py-2.5">
        <div class="flex items-baseline gap-2">
          <code
            class="text-xs font-mono text-accent bg-accent/10 px-1.5 py-0.5 rounded"
          >{{ tc.name }}</code>
          <span v-if="riskText(tc)" class="text-xs text-warning">{{ riskText(tc) }}</span>
        </div>
        <pre
          v-if="fmtArgs(tc.args)"
          class="mt-1.5 text-xs font-mono text-ink-muted bg-surface-muted rounded p-2 overflow-x-auto max-h-40 whitespace-pre-wrap break-all"
        >{{ fmtArgs(tc.args) }}</pre>
      </div>
    </div>

    <div class="px-4 py-2.5 flex items-center gap-2 bg-surface-muted/40 border-t border-border">
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
        <Check class="size-3.5" /> 仅批准本次
      </button>
    </div>
  </div>
</template>
