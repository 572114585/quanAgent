<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Settings, Plus, Search } from 'lucide-vue-next'
import { useTheme } from '@/composables/useTheme'
import { usePlatform } from '@/composables/usePlatform'
import { useSessionsStore } from '@/stores/sessions'
import { useShortcuts } from '@/composables/useShortcuts'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'
import SessionItem from '@/components/layout/SessionItem.vue'

const route = useRoute()
const router = useRouter()
useTheme()
const { isMobile } = usePlatform()
const sessions = useSessionsStore()

const sidebarOpen = ref(false)
const search = ref('')

// 派生状态用 computed，避免原 ref+watch+O(n) 字符串拼接的开销
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return q ? sessions.list.filter((s) => s.title.toLowerCase().includes(q)) : sessions.list
})

function closeSidebar() {
  sidebarOpen.value = false
}

function newChat() {
  const s = sessions.create()
  router.push({ name: 'session', params: { id: s.id } })
  closeSidebar()
}

function open(id: string) {
  router.push({ name: 'session', params: { id } })
  closeSidebar()
}

// 直接监听视口宽度，不依赖 isMobile 的异步 detect，避免 onMounted 顺序竞态
const mq = ref<MediaQueryList | null>(null)
const onChange = () => {
  if (mq.value?.matches) sidebarOpen.value = false
}
onMounted(() => {
  mq.value = window.matchMedia('(min-width: 768px)')
  mq.value.addEventListener('change', onChange)
})
onUnmounted(() => {
  mq.value?.removeEventListener('change', onChange)
})

// 路由变化时自动关闭移动端侧栏
watch(() => route.fullPath, closeSidebar)

useShortcuts([
  { combo: 'mod+k', description: '新建对话', handler: newChat },
  { combo: 'mod+/', description: '打开设置', handler: () => router.push({ name: 'settings' }) },
  // allowInInputs: false，避免在搜索框/重命名输入框按 Esc 时误关闭侧栏
  // （输入框内按 Esc 由元素自身处理，不触发关闭）
  { combo: 'escape', description: '关闭侧栏', allowInInputs: false, handler: closeSidebar }
])
</script>

<template>
  <div class="h-full w-full flex bg-surface text-ink overflow-hidden">
    <!-- Mobile backdrop -->
    <transition name="fade">
      <div
        v-if="isMobile && sidebarOpen"
        class="fixed inset-0 z-30 bg-black/50 md:hidden"
        aria-hidden="true"
        @click="closeSidebar"
      />
    </transition>

    <!-- Sidebar -->
    <aside
      :aria-label="isMobile && sidebarOpen ? '会话列表（抽屉）' : '主导航'"
      :role="isMobile && sidebarOpen ? 'dialog' : undefined"
      :aria-modal="isMobile && sidebarOpen ? 'true' : undefined"
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
          <Plus class="size-4" aria-hidden="true" /> 新建对话
        </button>
      </div>

      <div class="px-3 pb-2">
        <div class="relative">
          <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-ink-subtle" aria-hidden="true" />
          <input
            v-model="search"
            class="input-base pl-8 py-1.5 text-xs"
            type="search"
            placeholder="搜索会话…"
            aria-label="搜索会话"
          />
        </div>
      </div>

      <nav class="flex-1 overflow-y-auto px-2 pb-3 space-y-1" aria-label="历史会话列表">
        <p class="px-2 pt-2 pb-1 text-xs uppercase tracking-wider text-ink-muted">
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
          class="px-2 py-6 text-center text-xs text-ink-muted"
        >
          {{ search ? '没有匹配的会话' : '还没有会话，开始一个吧' }}
        </p>
      </nav>

      <div class="border-t border-border p-2 flex items-center justify-between">
        <ThemeToggle />
        <button
          class="btn-ghost p-2"
          aria-label="设置"
          @click="router.push({ name: 'settings' })"
        >
          <Settings class="size-4" aria-hidden="true" />
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
        <button class="btn-ghost p-2" aria-label="打开侧栏" @click="sidebarOpen = true">
          <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <span class="text-sm font-medium truncate">
          {{ sessions.active?.title || 'Agent' }}
        </span>
        <div class="ml-auto flex items-center gap-1">
          <button class="btn-ghost p-2" aria-label="新建对话" @click="newChat">
            <Plus class="size-4" aria-hidden="true" />
          </button>
        </div>
      </header>

      <main class="flex-1 min-h-0 overflow-hidden" tabindex="-1">
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
