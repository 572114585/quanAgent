<script setup lang="ts">
import { computed, reactive } from 'vue'
import { HelpCircle, Check } from 'lucide-vue-next'
import type {
  AskUserAnswer,
  AskUserQuestionItem,
  InterruptGroup,
  ResumeGroup
} from '@/types/domain'

const props = defineProps<{
  groups: InterruptGroup[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'decide', groups: ResumeGroup[]): void
}>()

const askGroups = computed(() =>
  props.groups.filter((g) => (g.kind || '') === 'ask_user_question' || (g.questions?.length ?? 0) > 0)
)

const title = computed(() => {
  const t = askGroups.value.map((g) => g.title).filter(Boolean)
  return t[0] || '需要你的确认'
})

const flatQuestions = computed(() => {
  const out: { groupId: string; q: AskUserQuestionItem }[] = []
  for (const g of askGroups.value) {
    for (const q of g.questions || []) {
      out.push({ groupId: g.interruptId, q })
    }
  }
  return out
})

/** questionId -> { selected, text } */
const draft = reactive<Record<string, { selected: string[]; text: string }>>({})

function ensureDraft(q: AskUserQuestionItem) {
  if (!draft[q.id]) {
    draft[q.id] = { selected: [], text: '' }
  }
  return draft[q.id]
}

function toggleOption(q: AskUserQuestionItem, opt: string) {
  const d = ensureDraft(q)
  if (q.allowMultiple) {
    const i = d.selected.indexOf(opt)
    if (i >= 0) d.selected.splice(i, 1)
    else d.selected.push(opt)
  } else {
    d.selected = [opt]
  }
}

function isSelected(q: AskUserQuestionItem, opt: string) {
  return ensureDraft(q).selected.includes(opt)
}

function submit() {
  const groups: ResumeGroup[] = askGroups.value.map((g) => {
    const answers: AskUserAnswer[] = (g.questions || []).map((q) => {
      const d = ensureDraft(q)
      let selected = [...d.selected]
      const text = d.text.trim()
      if (!selected.length && !text && q.options?.length) {
        selected = [q.options[0]]
      }
      if (!selected.length && !text) {
        selected = ['确认继续']
      }
      return { questionId: q.id, selected, text }
    })
    return {
      interruptId: g.interruptId,
      kind: 'ask_user_question' as const,
      answers
    }
  })
  emit('decide', groups)
}
</script>

<template>
  <div
    class="rounded-xl border border-border bg-surface-elevated/95 backdrop-blur-md overflow-hidden"
  >
    <div class="px-4 py-2.5 flex items-center gap-2 border-b border-border">
      <HelpCircle class="size-4 text-accent shrink-0" />
      <span class="text-sm font-medium text-ink">{{ title }}</span>
      <span class="text-xs text-ink-subtle ml-auto">{{ flatQuestions.length }} 题</span>
    </div>

    <div class="divide-y divide-border">
      <div
        v-for="{ q } in flatQuestions"
        :key="q.id"
        class="px-4 py-3 space-y-2"
      >
        <p class="text-sm text-ink">{{ q.prompt }}</p>
        <div v-if="q.options?.length" class="flex flex-wrap gap-2">
          <button
            v-for="opt in q.options"
            :key="opt"
            type="button"
            class="text-xs px-2.5 py-1.5 rounded-lg border transition-colors"
            :class="
              isSelected(q, opt)
                ? 'border-accent bg-accent/15 text-accent'
                : 'border-border text-ink-muted hover:border-accent/50'
            "
            :disabled="disabled"
            @click="toggleOption(q, opt)"
          >
            {{ opt }}
          </button>
        </div>
        <textarea
          v-if="q.allowFreeText !== false"
          v-model="ensureDraft(q).text"
          class="w-full text-xs font-mono text-ink bg-surface-muted rounded-lg p-2 border border-border resize-y min-h-[2.5rem] max-h-28"
          placeholder="补充说明（可选）"
          :disabled="disabled"
          rows="2"
        />
      </div>
    </div>

    <div class="px-4 py-2.5 flex items-center gap-2 bg-surface-muted/40 border-t border-border">
      <button
        class="btn-primary text-xs px-3 py-1.5 ml-auto"
        :disabled="disabled"
        @click="submit"
      >
        <Check class="size-3.5" /> 提交回答
      </button>
    </div>
  </div>
</template>
