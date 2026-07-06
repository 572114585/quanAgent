<script setup lang="ts">
import { ref, nextTick, watch, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Session, Attachment, ResumeGroup } from '@/types/domain'
import { Send, Square, Paperclip, Sparkles, Wand2, Code2, FileText, X, Loader2 } from 'lucide-vue-next'
import { useShortcuts } from '@/composables/useShortcuts'
import MessageBubble from './MessageBubble.vue'
import FloatingTodoList from './FloatingTodoList.vue'
import HitlApproval from './HitlApproval.vue'
import { useChatStore, type ChatMessage } from '@/stores/chat'
import { useSessionsStore } from '@/stores/sessions'
import { uploadFile } from '@/api/chat'

const props = defineProps<{ session: Session }>()

const chat = useChatStore()
const sessions = useSessionsStore()
const router = useRouter()

/** 视口 ≥ 768px 时主区足够宽，任务清单默认展开；否则默认折叠 */
const hasRoom = ref(false)
let mq: MediaQueryList | null = null
const onMqChange = () => {
  hasRoom.value = mq?.matches ?? false
}
onMounted(() => {
  mq = window.matchMedia('(min-width: 768px)')
  hasRoom.value = mq.matches
  mq.addEventListener('change', onMqChange)
})
onUnmounted(() => {
  mq?.removeEventListener('change', onMqChange)
})

const scrollEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)
const fileEl = ref<HTMLInputElement | null>(null)
const input = ref('')
const pendingAttachments = ref<Attachment[]>([])
const uploading = ref(false)

const messages = computed<ChatMessage[]>(() => chat.messagesBySession[props.session.id] ?? [])
const todos = computed(() => chat.todosBySession[props.session.id] ?? [])
const subagents = computed(() => chat.subagentTasksBySession[props.session.id] ?? [])

const pendingApprovalMsg = computed(() => {
  return messages.value.find((m) => m.status === 'awaiting_approval' && m.pendingInterruptGroups && m.pendingInterruptGroups.length > 0)
})
const pendingInterruptGroups = computed(() => pendingApprovalMsg.value?.pendingInterruptGroups ?? [])
const hasPendingApproval = computed(() => pendingInterruptGroups.value.length > 0)

const suggestedPrompts = [
  { icon: Wand2, label: '帮我写一段欢迎语', prompt: '帮我写一段简洁友好的产品欢迎语' },
  { icon: Code2, label: '解释这段代码', prompt: '请解释下面这段代码的作用：' },
  { icon: FileText, label: '总结一篇文档', prompt: '请帮我总结一份文档的核心要点' },
  { icon: Sparkles, label: '头脑风暴', prompt: '我们一起头脑风暴 5 个产品创意' }
]

const sending = computed(() => messages.value.some((m) => m.status === 'streaming' || m.status === 'awaiting_approval'))
const canSend = computed(() => !sending.value && !uploading.value && (input.value.trim() || pendingAttachments.value.length > 0) && pendingAttachments.value.every((a) => !!a.remoteUrl))

function scrollToBottom(smooth = true) {
  nextTick(() => {
    if (scrollEl.value)
      scrollEl.value.scrollTo({
        top: scrollEl.value.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto'
      })
  })
}

function autoSize() {
  const ta = inputEl.value
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
}

async function send(text?: string) {
  const content = (text ?? input.value).trim()
  if ((!content && pendingAttachments.value.length === 0) || sending.value || uploading.value) return
  if (pendingAttachments.value.some((a) => !a.remoteUrl)) return
  input.value = ''
  autoSize()
  const attachments = pendingAttachments.value
  pendingAttachments.value = []
  await chat.send(props.session.id, content, { attachments })
  scrollToBottom()
}

function stop() {
  chat.stop(props.session.id)
}

function pickFile() {
  fileEl.value?.click()
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return
  uploadAll(Array.from(target.files))
  target.value = ''
}

function uploadAll(files: File[]) {
  uploading.value = true
  Promise.all(
    files.map(async (f) => {
      const blobUrl = URL.createObjectURL(f)
      const local: Attachment = {
        id: 'a_' + Math.random().toString(36).slice(2, 10),
        name: f.name,
        mime: f.type || 'application/octet-stream',
        size: f.size,
        previewUrl: blobUrl
      }
      pendingAttachments.value.push(local)
      try {
        const result = await uploadFile(f)
        local.remoteUrl = result.url
        local.mime = result.mime
      } catch (err) {
        console.error('upload failed', err)
        local.remoteUrl = undefined
      }
    })
  ).finally(() => {
    uploading.value = false
  })
}

function removeAttachment(id: string) {
  pendingAttachments.value = pendingAttachments.value.filter((a) => a.id !== id)
}

function newChat() {
  sessions.create()
  router.push({ name: 'home' })
}

useShortcuts([
  { combo: 'mod+k', description: '新建对话', handler: newChat },
  {
    combo: 'enter',
    description: '发送消息',
    allowInInputs: false,
    handler: () => send()
  },
  {
    combo: 'shift+enter',
    description: '换行',
    allowInInputs: false,
    handler: () => {
      input.value += '\n'
      autoSize()
    }
  }
])

watch(
  () => messages.value.length,
  () => scrollToBottom(false)
)
watch(
  () => messages.value.map((m) => `${m.content.length}:${m.thinkingContent?.length ?? 0}:${m.artifacts?.length ?? 0}`).join(','),
  () => scrollToBottom()
)

onMounted(() => {
  scrollToBottom(false)
  input.value = ''
})

function onDecide(groups: ResumeGroup[]) {
  void chat.resume(props.session.id, groups)
}
</script>

<template>
  <div class="relative flex flex-col h-full min-h-0">
    <!-- 主体：聊天区 + 任务清单区，各占独立区域不重叠 -->
    <div class="flex flex-1 min-h-0 flex-col md:flex-row">
      <!-- 聊天区容器：作为悬浮输入框的定位父级，输入框只悬浮在聊天记录上方 -->
      <div class="relative flex flex-1 flex-col min-h-0 md:order-1">
        <!-- 聊天滚动区：底部留出悬浮输入框的空间；HITL 出现时额外加大留白 -->
        <div
          ref="scrollEl"
          class="flex-1 overflow-y-auto px-4 md:px-8 py-6"
          :class="hasPendingApproval ? 'pb-72' : 'pb-40'"
        >
          <!-- Empty state -->
          <div
            v-if="messages.length === 0"
            class="h-full flex items-center justify-center min-h-[60vh]"
          >
            <div class="max-w-2xl w-full text-center space-y-6 animate-slide-up">
              <div
                class="inline-flex size-14 rounded-2xl bg-gradient-to-br from-accent to-accent/60 items-center justify-center text-white shadow-lg"
              >
                <Sparkles class="size-6" />
              </div>
              <div>
                <h2 class="text-xl font-semibold text-ink">有什么可以帮你的？</h2>
                <p class="text-sm text-ink-muted mt-1.5">选一个起点，或者直接输入你的问题</p>
              </div>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <button
                  v-for="(p, i) in suggestedPrompts"
                  :key="i"
                  class="group flex items-center gap-3 px-4 py-3 rounded-xl border border-border bg-surface-elevated hover:bg-surface-muted hover:border-border-strong transition-colors text-left"
                  @click="send(p.prompt)"
                >
                  <component
                    :is="p.icon"
                    class="size-4 text-ink-subtle group-hover:text-accent transition-colors shrink-0"
                  />
                  <div>
                    <p class="text-sm text-ink font-medium">{{ p.label }}</p>
                    <p class="text-xs text-ink-subtle mt-0.5 line-clamp-1">{{ p.prompt }}</p>
                  </div>
                </button>
              </div>
            </div>
          </div>

          <!-- Messages -->
          <div v-else class="max-w-3xl mx-auto space-y-6">
            <MessageBubble
              v-for="m in messages"
              :key="m.id"
              :role="m.role"
              :content="m.content"
              :thinking-content="m.thinkingContent"
              :has-thought="m.hasThought"
              :tool-calls="m.toolCalls"
              :hitl-note="m.hitlNote"
              :status="m.status"
              :error="m.error"
              :attachments="m.attachments"
              :artifacts="m.artifacts"
              :kb-references="m.kbReferences"
              :can-regenerate="m.role === 'assistant' && (m.status === 'complete' || m.status === 'cancelled' || (m.artifacts && m.artifacts.length > 0))"
              @regenerate="chat.regenerate(props.session.id)"
            />
          </div>
        </div>

        <!-- 悬浮输入框：相对聊天区容器定位，只悬浮在聊天记录上方 -->
        <div class="absolute bottom-0 left-0 right-0 z-20 pointer-events-none">
          <!-- 悬浮 HITL 确认框：紧贴输入框上方，宽度对齐 -->
          <div
            v-if="hasPendingApproval"
            class="max-w-3xl mx-auto px-3 md:px-4 pb-2 pointer-events-auto animate-slide-up"
          >
            <HitlApproval
              :groups="pendingInterruptGroups"
              class="shadow-xl shadow-black/10"
              @decide="onDecide"
            />
          </div>
          <!-- 渐变遮罩 + 毛玻璃：宽度对齐表单，不盖住滚动条 -->
          <div class="max-w-3xl mx-auto px-3 md:px-4 pointer-events-none">
            <div class="h-8 bg-gradient-to-t from-surface to-transparent"></div>
            <div class="bg-surface/80 backdrop-blur-sm rounded-t-2xl">
              <div class="pb-3 md:pb-5 pt-1 px-1 pointer-events-auto">
                <!-- Pending attachments -->
                <div
                  v-if="pendingAttachments.length"
                  class="mb-2 flex flex-wrap gap-2 justify-center"
                >
                  <div
                    v-for="a in pendingAttachments"
                    :key="a.id"
                    class="relative group rounded-lg border border-border bg-surface-elevated/95 backdrop-blur-sm overflow-hidden shadow-md"
                  >
                    <img
                      v-if="a.mime.startsWith('image/')"
                      :src="a.previewUrl || a.remoteUrl"
                      :alt="a.name"
                      class="size-14 object-cover"
                    />
                    <div
                      v-else
                      class="px-3 h-14 flex items-center gap-1.5 text-xs text-ink-muted max-w-[180px]"
                    >
                      <Paperclip class="size-3.5 shrink-0" />
                      <span class="truncate">{{ a.name }}</span>
                    </div>
                    <button
                      class="absolute top-0.5 right-0.5 p-0.5 rounded bg-black/50 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      aria-label="移除附件"
                      @click="removeAttachment(a.id)"
                    >
                      <X class="size-3" />
                    </button>
                    <div
                      v-if="!a.remoteUrl"
                      class="absolute inset-0 bg-black/40 flex items-center justify-center"
                    >
                      <Loader2 class="size-4 text-white animate-spin" />
                    </div>
                  </div>
                </div>

                <!-- 输入框主体 -->
                <form
                  class="flex items-end gap-2 bg-surface-elevated/95 backdrop-blur-md border border-border rounded-2xl p-2 shadow-xl shadow-black/10 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 transition-all"
                  @submit.prevent="send()"
                >
                  <button
                    type="button"
                    class="btn-ghost p-2 shrink-0"
                    aria-label="附件"
                    :disabled="sending || uploading"
                    @click="pickFile"
                  >
                    <Paperclip class="size-4" />
                  </button>
                  <input
                    ref="fileEl"
                    type="file"
                    class="hidden"
                    accept="image/*,.pdf,.txt,.md,.docx,.doc,.xlsx,.xls,.csv,.json,.ppt,.pptx"
                    multiple
                    @change="onFileChange"
                  />
                  <textarea
                    ref="inputEl"
                    v-model="input"
                    rows="1"
                    class="flex-1 resize-none bg-transparent text-sm text-ink placeholder:text-ink-subtle focus:outline-none px-2 py-2 max-h-40"
                    placeholder="发消息…  (Enter 发送，Shift+Enter 换行)"
                    @input="autoSize"
                    @keydown.enter.exact.prevent="send()"
                  />
                  <button
                    v-if="!sending"
                    type="submit"
                    class="btn-primary p-2 shrink-0"
                    :disabled="!canSend"
                    aria-label="发送"
                  >
                    <Send class="size-4" />
                  </button>
                  <button
                    v-else
                    type="button"
                    class="btn-primary p-2 shrink-0"
                    aria-label="停止"
                    @click="stop"
                  >
                    <Square class="size-4" />
                  </button>
                </form>
                <p class="text-center text-[11px] text-ink-subtle mt-2 hidden md:block">
                  按 <kbd class="kbd">⌘K</kbd> 新建对话 · <kbd class="kbd">Enter</kbd> 发送 · <kbd class="kbd">Shift+Enter</kbd> 换行
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 任务清单：移动端在顶部，桌面端在右侧 -->
      <FloatingTodoList :todos="todos" :subagents="subagents" :default-expanded="hasRoom" />
    </div>
  </div>
</template>

<style scoped>
.kbd {
  display: inline-block;
  padding: 0 0.35em;
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 0.75em;
  border: 1px solid rgb(var(--border));
  border-bottom-width: 2px;
  border-radius: 4px;
  background: rgb(var(--surface-muted));
  color: rgb(var(--ink-muted));
}
</style>
