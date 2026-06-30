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
const menuBtnRef = ref<HTMLButtonElement | null>(null)
const rootEl = ref<HTMLDivElement | null>(null)
let closeHandler: ((ev: MouseEvent) => void) | null = null

function removeCloseHandler() {
  if (closeHandler) {
    document.removeEventListener('click', closeHandler)
    closeHandler = null
  }
}

/**
 * 切换菜单。打开时聚焦第一个 menuitem（WAI-ARIA Menu Pattern），
 * 关闭时可选还原焦点到触发器。
 */
function toggleMenu() {
  if (menuOpen.value) {
    closeMenu(false)
    return
  }
  menuOpen.value = true
  scheduleClose()
  nextTick(() => {
    rootEl.value?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus()
  })
}

function closeMenu(restoreFocus: boolean) {
  menuOpen.value = false
  removeCloseHandler()
  if (restoreFocus) menuBtnRef.value?.focus()
}

function scheduleClose() {
  removeCloseHandler()
  closeHandler = (ev: MouseEvent) => {
    if (!rootEl.value) return
    if (!rootEl.value.contains(ev.target as Node)) {
      closeMenu(false)
    }
  }
  nextTick(() => {
    if (closeHandler) document.addEventListener('click', closeHandler)
  })
}

/** 菜单键盘：Escape 关闭并还原焦点；方向键可在 menuitem 间切换。 */
function onMenuKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    closeMenu(true)
    return
  }
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault()
    const items = rootEl.value?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')
    if (!items || items.length === 0) return
    const idx = Array.from(items).findIndex((el) => el === document.activeElement)
    const next = e.key === 'ArrowDown' ? (idx + 1) % items.length : (idx - 1 + items.length) % items.length
    items[next]?.focus()
  }
}

onBeforeUnmount(() => {
  removeCloseHandler()
})

function startEdit() {
  menuOpen.value = false
  removeCloseHandler()
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

function confirmRemove() {
  menuOpen.value = false
  removeCloseHandler()
  // TODO: 替换为自定义对话框组件（原生 confirm 阻塞主线程且不可主题化）
  if (confirm(`删除会话「${props.session.title}」？`)) emit('remove', props.session.id)
}

function onClick() {
  if (editing.value) return
  emit('open', props.session.id)
}
</script>

<template>
  <div ref="rootEl" class="relative group">
    <!-- 非编辑态：主按钮（独立，不嵌套 input/菜单触发器） -->
    <button
      v-if="!editing"
      :class="[
        'w-full flex items-start gap-2 px-2 py-2 rounded-lg text-left text-sm transition-colors',
        active
          ? 'bg-accent-soft text-accent'
          : 'text-ink-muted hover:bg-surface-muted'
      ]"
      :aria-current="active ? 'true' : undefined"
      @click="onClick"
      @dblclick="startEdit"
    >
      <MessageSquare class="size-4 mt-0.5 shrink-0" aria-hidden="true" />
      <span class="line-clamp-2 break-all flex-1">
        {{ session.title || '新对话' }}
      </span>
    </button>

    <!-- 菜单触发器：独立 button，避免 button 嵌套 -->
    <button
      v-if="!editing"
      ref="menuBtnRef"
      type="button"
      class="absolute right-1 top-2 p-1 rounded-md text-ink-subtle hover:text-ink hover:bg-surface-muted opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
      :aria-haspopup="true"
      :aria-expanded="menuOpen"
      :aria-controls="`session-menu-${session.id}`"
      aria-label="更多操作"
      @click.stop="toggleMenu"
    >
      <MoreHorizontal class="size-4" aria-hidden="true" />
    </button>

    <!-- 编辑态：input 与按钮分离，不在 button 内 -->
    <div
      v-else
      :class="[
        'flex items-start gap-2 px-2 py-2 rounded-lg text-sm',
        active ? 'bg-accent-soft' : 'bg-surface-muted'
      ]"
    >
      <MessageSquare class="size-4 mt-0.5 shrink-0 text-ink-subtle" aria-hidden="true" />
      <input
        ref="inputEl"
        v-model="draftTitle"
        class="flex-1 min-w-0 bg-transparent text-sm text-ink focus:outline-none focus:ring-1 focus:ring-accent/40 rounded px-1 -mx-1"
        :aria-label="`重命名会话：${session.title}`"
        @keydown.enter.prevent="commit"
        @keydown.escape.prevent="cancel"
        @blur="commit"
      />
    </div>

    <transition name="pop">
      <div
        v-if="menuOpen"
        :id="`session-menu-${session.id}`"
        role="menu"
        class="absolute right-1 top-9 z-20 min-w-[120px] rounded-lg border border-border bg-surface-elevated shadow-lg py-1 text-sm"
        @click.stop
        @keydown="onMenuKeydown"
      >
        <button
          role="menuitem"
          class="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-surface-muted text-ink-muted focus:bg-surface-muted focus:outline-none"
          @click="startEdit"
        >
          <Pencil class="size-3.5" aria-hidden="true" /> 重命名
        </button>
        <button
          role="menuitem"
          class="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-surface-muted text-danger focus:bg-surface-muted focus:outline-none"
          @click="confirmRemove"
        >
          <Trash2 class="size-3.5" aria-hidden="true" /> 删除
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
