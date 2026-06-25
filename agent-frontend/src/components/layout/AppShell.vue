<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Settings, Plus, Search } from 'lucide-vue-next'
import { useTheme } from '@/composables/useTheme'
import { usePlatform } from '@/composables/usePlatform'
import { useSessionsStore } from '@/stores/sessions'
import { useShortcuts } from '@/composables/useShortcuts'
import type { Session } from '@/types/domain'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'
import SessionItem from '@/components/layout/SessionItem.vue'

const route = useRoute()
const router = useRouter()
useTheme()
const { isMobile } = usePlatform()
const sessions = useSessionsStore()

const sidebarOpen = ref(false)
const search = ref('')

const filtered = ref<Session[]>([])
function recompute() {
  const q = search.value.trim().toLowerCase()
  filtered.value = q
    ? sessions.list.filter((s) => s.title.toLowerCase().includes(q))
    : sessions.list
}
watch(() => [sessions.list.length, sessions.list.map((s) => s.title).join('|'), search.value], recompute, { immediate: true })

function closeSidebar() {
  sidebarOpen.value = false
}

function newChat() {
  sessions.create()
  router.push({ name: 'home' })
  closeSidebar()
}

function open(id: string) {
  router.push({ name: 'session', params: { id } })
  closeSidebar()
}

const mq = ref<MediaQueryList | null>(null)
const onChange = () => {
  if (mq.value?.matches && isMobile.value) sidebarOpen.value = false
}
onMounted(() => {
  sessions.load()
  if (isMobile.value) {
    mq.value = window.matchMedia('(min-width: 768px)')
    mq.value.addEventListener('change', onChange)
  }
})
onUnmounted(() => {
  mq.value?.removeEventListener('change', onChange)
})

useShortcuts([
  { combo: 'mod+k', description: '新建对话', handler: newChat },
  { combo: 'mod+/', description: '打开设置', handler: () => router.push({ name: 'settings' }) },
  { combo: 'escape', description: '关闭侧栏', allowInInputs: true, handler: closeSidebar }
])
</script>

<template>
  <div class="h-full w-full flex bg-surface text-ink overflow-hidden">
    <!-- Mobile backdrop -->
    <transition name="fade">
      <div
        v-if="isMobile && sidebarOpen"
        class="fixed inset-0 z-30 bg-black/50 md:hidden"
        @click="closeSidebar"
      />
    </transition>

    <!-- Sidebar -->
    <aside
      :class="[
        'shrink-0 border-r border-border bg-surface-elevated flex flex-col',
        isMobile
          ? 'fixed inset-y-0 left-0 z-40 w-72 transform transition-transform duration-200'
          : 'w-64',
        isMobile && !sidebarOpen ? '-translate-x-full' : 'translate-x-0'
      ]"
    >
      <div class="p-3 flex items-center gap-2">
        <button class="btn-primary flex-1 justify-start" @click="newChat">
          <Plus class="size-4" /> 新建对话
        </button>
      </div>

      <div class="px-3 pb-2">
        <div class="relative">
          <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-ink-subtle" />
          <input
            v-model="search"
            class="input-base pl-8 py-1.5 text-xs"
            placeholder="搜索会话…"
          />
        </div>
      </div>

      <nav class="flex-1 overflow-y-auto px-2 pb-3 space-y-1">
        <p class="px-2 pt-2 pb-1 text-xs uppercase tracking-wider text-ink-subtle">
          历史会话
        </p>
        <SessionItem
          v-for="s in filtered"
          :key="s.id"
          :session="s"
          :active="route.params.id === s.id || (route.name === 'home' && sessions.activeId === s.id)"
          @open="open"
          @rename="(id, t) => sessions.rename(id, t)"
          @remove="(id) => sessions.remove(id)"
        />
        <p
          v-if="filtered.length === 0"
          class="px-2 py-6 text-center text-xs text-ink-subtle"
        >
          {{ search ? '没有匹配的会话' : '还没有会话，开始一个吧' }}
        </p>
      </nav>

      <div class="border-t border-border p-2 flex items-center justify-between">
        <ThemeToggle />
        <button
          class="btn-ghost p-2"
          :aria-label="'设置'"
          @click="router.push({ name: 'settings' })"
        >
          <Settings class="size-4" />
        </button>
      </div>
    </aside>

    <!-- Main -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Mobile top bar -->
      <header
        v-if="isMobile"
        class="md:hidden flex items-center gap-2 px-3 h-12 border-b border-border bg-surface-elevated"
      >
        <button class="btn-ghost p-2" @click="sidebarOpen = true" aria-label="打开侧栏">
          <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <span class="text-sm font-medium truncate">
          {{ sessions.active?.title || 'Agent' }}
        </span>
        <div class="ml-auto flex items-center gap-1">
          <button class="btn-ghost p-2" @click="newChat" aria-label="新建对话">
            <Plus class="size-4" />
          </button>
        </div>
      </header>

      <main class="flex-1 min-h-0 overflow-hidden">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
