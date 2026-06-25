<script setup lang="ts">
import { ref, nextTick, onBeforeUnmount } from 'vue'
import { MoreHorizontal, Pencil, Trash2, MessageSquare } from 'lucide-vue-next'
import type { Session } from '@/types/domain'

const props = defineProps<{
  session: Session
  active: boolean
}>()

const emit = defineEmits<{
  (e: 'open', id: string): void
  (e: 'rename', id: string, title: string): void
  (e: 'remove', id: string): void
}>()

const menuOpen = ref(false)
const editing = ref(false)
const draftTitle = ref('')
const inputEl = ref<HTMLInputElement | null>(null)
const rootEl = ref<HTMLDivElement | null>(null)
let closeHandler: ((ev: MouseEvent) => void) | null = null

function removeCloseHandler() {
  if (closeHandler) {
    document.removeEventListener('click', closeHandler)
    closeHandler = null
  }
}

function toggleMenu(e: Event) {
  e.stopPropagation()
  menuOpen.value = !menuOpen.value
  if (menuOpen.value) {
    scheduleClose()
  } else {
    removeCloseHandler()
  }
}

function scheduleClose() {
  removeCloseHandler()
  closeHandler = (ev: MouseEvent) => {
    if (!rootEl.value) return
    if (!rootEl.value.contains(ev.target as Node)) {
      menuOpen.value = false
      removeCloseHandler()
    }
  }
  nextTick(() => {
    if (closeHandler) document.addEventListener('click', closeHandler)
  })
}

onBeforeUnmount(() => {
  removeCloseHandler()
})

function startEdit(e: Event) {
  e.stopPropagation()
  menuOpen.value = false
  draftTitle.value = props.session.title
  editing.value = true
  nextTick(() => {
    inputEl.value?.focus()
    inputEl.value?.select()
  })
}

function commit() {
  if (!editing.value) return
  editing.value = false
  const next = draftTitle.value.trim()
  if (next && next !== props.session.title) emit('rename', props.session.id, next)
}

function cancel() {
  editing.value = false
  draftTitle.value = props.session.title
}

function confirmRemove(e: Event) {
  e.stopPropagation()
  menuOpen.value = false
  if (confirm(`删除会话「${props.session.title}」？`)) emit('remove', props.session.id)
}

function onClick() {
  if (editing.value) return
  emit('open', props.session.id)
}
</script>

<template>
  <div ref="rootEl" class="relative group">
    <button
      :class="[
        'w-full flex items-start gap-2 px-2 py-2 rounded-lg text-left text-sm transition-colors',
        active
          ? 'bg-accent-soft text-accent'
          : 'text-ink-muted hover:bg-surface-muted'
      ]"
      @click="onClick"
      @dblclick="startEdit"
    >
      <MessageSquare class="size-4 mt-0.5 shrink-0" />
      <input
        v-if="editing"
        ref="inputEl"
        v-model="draftTitle"
        class="flex-1 min-w-0 bg-transparent text-sm text-ink focus:outline-none focus:ring-1 focus:ring-accent/40 rounded px-1 -mx-1"
        @click.stop
        @keydown.enter.prevent="commit"
        @keydown.escape.prevent="cancel"
        @blur="commit"
      />
      <span v-else class="line-clamp-2 break-all flex-1">
        {{ session.title || '新对话' }}
      </span>
      <span
        v-if="!editing"
        class="opacity-0 group-hover:opacity-100 transition-opacity"
        @click.stop="toggleMenu"
      >
        <MoreHorizontal class="size-4 text-ink-subtle" />
      </span>
    </button>

    <transition name="pop">
      <div
        v-if="menuOpen"
        class="absolute right-1 top-9 z-20 min-w-[120px] rounded-lg border border-border bg-surface-elevated shadow-lg py-1 text-sm"
        @click.stop
      >
        <button
          class="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-surface-muted text-ink-muted"
          @click="startEdit"
        >
          <Pencil class="size-3.5" /> 重命名
        </button>
        <button
          class="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-surface-muted text-danger"
          @click="confirmRemove"
        >
          <Trash2 class="size-3.5" /> 删除
        </button>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: scale(0.96) translateY(-2px);
}
</style>
