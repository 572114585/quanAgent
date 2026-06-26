<script setup lang="ts">
import { ref, nextTick, watch, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Session, Attachment } from '@/types/domain'
import { Send, Square, Paperclip, Sparkles, Wand2, Code2, FileText, X, Loader2 } from 'lucide-vue-next'
import { useShortcuts } from '@/composables/useShortcuts'
import MessageBubble from './MessageBubble.vue'
import { useChatStore, type ChatMessage } from '@/stores/chat'
import { useSessionsStore } from '@/stores/sessions'
import { uploadFile } from '@/api/chat'

const props = defineProps<{ session: Session }>()

const chat = useChatStore()
const sessions = useSessionsStore()
const router = useRouter()

const scrollEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)
const fileEl = ref<HTMLInputElement | null>(null)
const input = ref('')
const pendingAttachments = ref<Attachment[]>([])
const uploading = ref(false)

const messages = computed<ChatMessage[]>(() => chat.messagesBySession[props.session.id] ?? [])

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

function onDecide(_messageId: string, decisions: Array<{ type: 'approve' | 'reject' }>) {
  void chat.resume(props.session.id, decisions)
}
</script>

<template>
  <div class="flex flex-col h-full min-h-0">
    <!-- Scroll area -->
    <div ref="scrollEl" class="flex-1 overflow-y-auto px-4 md:px-8 py-6">
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
          :pending-tool-calls="m.pendingToolCalls"
          :can-regenerate="m.role === 'assistant' && (m.status === 'complete' || m.status === 'cancelled' || (m.artifacts && m.artifacts.length > 0))"
          @regenerate="chat.regenerate(props.session.id)"
          @decide="(d) => onDecide(m.id, d)"
        />
      </div>
    </div>

    <!-- Composer -->
    <div class="border-t border-border bg-surface-elevated/80 backdrop-blur p-3 md:p-4">
      <!-- Pending attachments -->
      <div
        v-if="pendingAttachments.length"
        class="max-w-3xl mx-auto mb-2 flex flex-wrap gap-2"
      >
        <div
          v-for="a in pendingAttachments"
          :key="a.id"
          class="relative group rounded-lg border border-border bg-surface-elevated overflow-hidden"
        >
          <img
            v-if="a.mime.startsWith('image/')"
            :src="a.previewUrl || a.remoteUrl"
            :alt="a.name"
            class="size-16 object-cover"
          />
          <div
            v-else
            class="px-3 h-16 flex items-center gap-1.5 text-xs text-ink-muted max-w-[200px]"
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

      <form
        class="max-w-3xl mx-auto flex items-end gap-2 bg-surface border border-border rounded-2xl p-2 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 transition-all"
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
