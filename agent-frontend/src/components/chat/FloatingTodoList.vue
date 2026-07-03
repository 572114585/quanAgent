<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CheckCircle2, Circle, Loader2, ChevronDown, ListTodo, Bot, Wrench } from 'lucide-vue-next'
import type { TodoItem, SubagentTask, SubagentStep } from '@/types/domain'

const props = defineProps<{
  todos: TodoItem[]
  /** 子智能体任务列表（并行子 agent = 数组多元素） */
  subagents?: SubagentTask[]
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

const subagentList = computed<SubagentTask[]>(() => props.subagents ?? [])
const subagentCount = computed(() => subagentList.value.length)
const runningSubagents = computed(() => subagentList.value.filter((s) => s.status === 'running'))
const currentSubagent = computed(() => runningSubagents.value[0])
const subagentCompletedCount = computed(() => subagentList.value.filter((s) => s.status === 'completed').length)

const hasContent = computed(() => totalCount.value > 0 || subagentCount.value > 0)
const allDone = computed(
  () =>
    hasContent.value &&
    completedCount.value === totalCount.value &&
    subagentCompletedCount.value === subagentCount.value
)

/** defaultExpanded 变化时同步（响应父级视口变化） */
watch(
  () => props.defaultExpanded,
  (v) => {
    expanded.value = v ?? false
  }
)

/** 全部完成时自动折叠（todos 与 subagents 都完成） */
watch(
  () => [
    props.todos.map((t) => t.status).join(','),
    subagentList.value.map((s) => s.status).join(',')
  ].join('|'),
  () => {
    if (
      hasContent.value &&
      completedCount.value === totalCount.value &&
      subagentCompletedCount.value === subagentCount.value
    ) {
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

function stepIcon(status: SubagentStep['status']) {
  switch (status) {
    case 'completed':
      return CheckCircle2
    case 'running':
      return Loader2
    case 'failed':
    default:
      return Circle
  }
}

function stepClass(status: SubagentStep['status']): string {
  switch (status) {
    case 'completed':
      return 'text-accent'
    case 'running':
      return 'text-warning'
    case 'failed':
    default:
      return 'text-danger'
  }
}

/** 把工具入参里的 query / description 等关键字段提取成短摘要，便于一眼看出子 agent 在搜什么 */
function stepSummary(step: SubagentStep): string {
  if (!step.args) return ''
  let obj: any
  if (typeof step.args === 'string') {
    try {
      obj = JSON.parse(step.args)
    } catch {
      return String(step.args).slice(0, 60)
    }
  } else {
    obj = step.args
  }
  if (!obj || typeof obj !== 'object') return ''
  // 常见字段优先级
  const candidates = ['query', 'q', 'description', 'topic', 'content', 'path', 'file_path']
  for (const k of candidates) {
    if (typeof obj[k] === 'string' && obj[k]) {
      return obj[k].slice(0, 60)
    }
  }
  return ''
}
</script>

<template>
  <div
    v-if="hasContent"
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
            <span v-else-if="currentSubagent" class="text-xs text-ink-muted truncate">
              子智能体：<span class="text-ink font-medium">{{ currentSubagent.subagentType }}</span>
              · {{ currentSubagent.description }}
            </span>
            <span v-else-if="allDone" class="text-xs text-success truncate">
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
          {{ completedCount + subagentCompletedCount }}/{{ totalCount + subagentCount }}
        </span>
        <ChevronDown
          class="size-3.5 shrink-0 text-ink-subtle transition-transform duration-200"
          :class="{ 'rotate-180': expanded }"
        />
      </button>

      <!-- 展开态：任务列表 + 子智能体分区 -->
      <div
        v-show="expanded"
        class="border-t border-border bg-surface-muted/30 max-h-[50vh] overflow-y-auto"
      >
        <!-- 主 agent 待办列表 -->
        <ol v-if="totalCount > 0" class="py-1">
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

        <!-- 子智能体分区（融入同一面板，与 todos 用分隔线区分） -->
        <div v-if="subagentCount > 0" class="border-t border-border/70 mt-1 pt-1 pb-1.5">
          <div class="flex items-center gap-1.5 px-3 pb-1">
            <Bot class="size-3.5 shrink-0 text-info" />
            <span class="text-[11px] font-medium text-ink-muted">子智能体</span>
            <span
              class="ml-auto shrink-0 text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-surface-muted text-ink-muted tabular-nums"
            >
              {{ subagentCompletedCount }}/{{ subagentCount }}
            </span>
          </div>

          <div
            v-for="sub in subagentList"
            :key="sub.id"
            class="mx-2 mb-1.5 rounded-lg border border-border/60 bg-surface-elevated/80 overflow-hidden"
            :class="{ 'border-info/40': sub.status === 'running' }"
          >
            <!-- 卡片头部 -->
            <div class="flex items-start gap-2 px-2.5 py-1.5">
              <component
                :is="sub.status === 'running' ? Loader2 : CheckCircle2"
                class="size-3.5 shrink-0 mt-0.5"
                :class="[
                  sub.status === 'running' ? 'text-info' : 'text-accent',
                  { 'animate-spin': sub.status === 'running' }
                ]"
              />
              <div class="flex-1 min-w-0">
                <p class="text-[11px] font-mono text-info leading-tight">{{ sub.subagentType }}</p>
                <p
                  class="text-xs leading-relaxed break-words mt-0.5"
                  :class="{
                    'text-ink font-medium': sub.status === 'running',
                    'text-ink-muted': sub.status === 'completed'
                  }"
                >
                  {{ sub.description }}
                </p>
              </div>
            </div>
            <!-- 嵌套步骤 -->
            <ul v-if="sub.steps.length > 0" class="border-t border-border/40 px-2.5 py-1 space-y-1">
              <li
                v-for="step in sub.steps"
                :key="step.id"
                class="flex items-start gap-1.5"
              >
                <component
                  :is="stepIcon(step.status)"
                  class="size-3 shrink-0 mt-0.5"
                  :class="[stepClass(step.status), { 'animate-spin': step.status === 'running' }]"
                />
                <div class="flex-1 min-w-0">
                  <p class="text-[11px] leading-tight">
                    <Wrench class="inline size-2.5 mr-1 text-ink-subtle align-text-bottom" />
                    <span class="font-mono text-ink-muted">{{ step.name }}</span>
                    <span v-if="stepSummary(step)" class="text-ink-subtle"> · {{ stepSummary(step) }}</span>
                  </p>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
