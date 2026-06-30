<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CheckCircle2, Circle, Loader2, ChevronDown, ListTodo } from 'lucide-vue-next'
import type { TodoItem } from '@/types/domain'

const props = defineProps<{
  todos: TodoItem[]
  /**
   * 空间够（桌面端主区 ≥ 768px）时是否默认展开。
   * 由父级 ChatPanel 根据视口判断后传入，CSS 媒体查询会负责切换宽度。
   */
  defaultExpanded?: boolean
}>()

const expanded = ref(props.defaultExpanded ?? false)

const completedCount = computed(() => props.todos.filter((t) => t.status === 'completed').length)
const totalCount = computed(() => props.todos.length)
const inProgressTodos = computed(() => props.todos.filter((t) => t.status === 'in_progress'))
const currentTask = computed(() => inProgressTodos.value[0])

/** defaultExpanded 变化时同步（响应父级视口变化） */
watch(
  () => props.defaultExpanded,
  (v) => {
    expanded.value = v ?? false
  }
)

/** 全部完成时自动折叠 */
watch(
  () => props.todos.map((t) => t.status).join(','),
  () => {
    if (totalCount.value > 0 && completedCount.value === totalCount.value) {
      expanded.value = false
    }
  }
)

function toggle() {
  expanded.value = !expanded.value
}

function statusIcon(status: TodoItem['status']) {
  switch (status) {
    case 'completed':
      return CheckCircle2
    case 'in_progress':
      return Loader2
    case 'pending':
    default:
      return Circle
  }
}

function statusClass(status: TodoItem['status']): string {
  switch (status) {
    case 'completed':
      return 'text-accent'
    case 'in_progress':
      return 'text-warning'
    case 'pending':
    default:
      return 'text-ink-subtle'
  }
}

function statusLabel(status: TodoItem['status']): string {
  switch (status) {
    case 'completed':
      return '已完成'
    case 'in_progress':
      return '进行中'
    case 'pending':
    default:
      return '待开始'
  }
}
</script>

<template>
  <div
    v-if="totalCount > 0"
    class="absolute top-3 right-3 z-30 w-[min(80%,320px)] md:w-72 animate-slide-up"
  >
    <div
      class="rounded-xl border border-border bg-surface-elevated/95 backdrop-blur-md shadow-lg overflow-hidden"
    >
      <!-- 折叠态/展开态共用头部：点击切换 -->
      <button
        class="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-surface-muted/60 transition-colors"
        @click="toggle"
      >
        <ListTodo class="size-4 shrink-0 text-accent" />
        <!-- 折叠态：当前任务 + 进度计数；展开态：标题 + 进度计数 -->
        <div class="flex-1 min-w-0 flex items-center gap-2">
          <template v-if="!expanded">
            <span v-if="currentTask" class="text-xs text-ink-muted truncate">
              正在：<span class="text-ink font-medium">{{ currentTask.content }}</span>
            </span>
            <span v-else-if="completedCount === totalCount" class="text-xs text-success truncate">
              全部完成
            </span>
            <span v-else class="text-xs text-ink-subtle truncate">任务进行中…</span>
          </template>
          <template v-else>
            <span class="text-xs font-medium text-ink">任务清单</span>
          </template>
        </div>
        <!-- 进度计数徽章 -->
        <span
          class="shrink-0 text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-surface-muted text-ink-muted tabular-nums"
        >
          {{ completedCount }}/{{ totalCount }}
        </span>
        <ChevronDown
          class="size-3.5 shrink-0 text-ink-subtle transition-transform duration-200"
          :class="{ 'rotate-180': expanded }"
        />
      </button>

      <!-- 展开态：全部任务列表 -->
      <div
        v-show="expanded"
        class="border-t border-border bg-surface-muted/30 max-h-[50vh] overflow-y-auto"
      >
        <ol class="py-1">
          <li
            v-for="(todo, idx) in todos"
            :key="idx"
            class="flex items-start gap-2 px-3 py-1.5"
            :class="{
              'opacity-50': todo.status === 'completed',
              'bg-accent/5': todo.status === 'in_progress'
            }"
          >
            <component
              :is="statusIcon(todo.status)"
              class="size-3.5 shrink-0 mt-0.5"
              :class="[statusClass(todo.status), { 'animate-spin': todo.status === 'in_progress' }]"
            />
            <div class="flex-1 min-w-0">
              <p
                class="text-xs leading-relaxed break-words"
                :class="{
                  'line-through text-ink-subtle': todo.status === 'completed',
                  'text-ink font-medium': todo.status === 'in_progress',
                  'text-ink-muted': todo.status === 'pending'
                }"
              >
                {{ todo.content }}
              </p>
            </div>
            <span
              class="shrink-0 text-[10px] mt-0.5"
              :class="statusClass(todo.status)"
            >
              {{ statusLabel(todo.status) }}
            </span>
          </li>
        </ol>
      </div>
    </div>
  </div>
</template>
