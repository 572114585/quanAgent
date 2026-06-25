<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Copy, Check, RefreshCw, AlertCircle, User, Sparkles, Ban, FileCheck, FileText, FileSpreadsheet, FileCode, Presentation, ChevronDown, Brain } from 'lucide-vue-next'
import { useMarkdown } from '@/composables/useMarkdown'
import type { ToolCallRequest, ArtifactFile } from '@/types/domain'
import HitlApproval from './HitlApproval.vue'
import FileAttachment from './FileAttachment.vue'

const props = defineProps<{
  role: 'user' | 'assistant' | 'system'
  content: string
  thinkingContent?: string
  hasThought?: boolean
  status?: 'pending' | 'streaming' | 'complete' | 'error' | 'cancelled' | 'awaiting_approval'
  error?: string
  attachments?: Array<{ id: string; name: string; mime: string; size: number; previewUrl?: string; remoteUrl?: string }>
  artifacts?: ArtifactFile[]
  pendingToolCalls?: ToolCallRequest[]
  canRegenerate?: boolean
}>()

const emit = defineEmits<{
  (e: 'regenerate'): void
  (e: 'decide', decisions: Array<{ type: 'approve' | 'reject' }>): void
}>()

const contentRef = computed(() => props.content)
const { html } = useMarkdown(contentRef)

const thinkingContentRef = computed(() => props.thinkingContent || '')
const { html: thinkingHtml } = useMarkdown(thinkingContentRef)

const isUser = computed(() => props.role === 'user')
const isError = computed(() => props.status === 'error')
const isStreaming = computed(() => props.status === 'streaming')
const isCancelled = computed(() => props.status === 'cancelled')
const isAwaitingApproval = computed(() => props.status === 'awaiting_approval')
const hasContent = computed(() => !!(props.content && props.content.trim()))
const hasThinkingContent = computed(() => !!(props.thinkingContent && props.thinkingContent.trim()))
const hasArtifacts = computed(() => !!(props.artifacts && props.artifacts.length > 0))
const hasAttachments = computed(() => !!(props.attachments && props.attachments.length > 0))

const shouldShowThinking = computed(() => {
  if (isUser.value) return false
  if (hasThinkingContent.value) return true
  if (props.hasThought) return true
  if (isStreaming.value && !hasContent.value) return true
  return false
})

const isActivelyThinking = computed(() => {
  return isStreaming.value && !hasContent.value
})

const thinkingExpanded = ref(false)

watch(
  () => [isActivelyThinking.value, hasContent.value] as [boolean, boolean],
  ([thinking, answering], prev) => {
    const prevThinking = prev?.[0]
    const prevAnswering = prev?.[1]
    if (thinking && !answering) {
      thinkingExpanded.value = true
    } else if (!thinking && answering && prevThinking && !prevAnswering) {
      thinkingExpanded.value = false
    }
  },
  { immediate: true }
)

watch(
  () => props.status,
  (newStatus) => {
    if (newStatus === 'complete' || newStatus === 'cancelled') {
      if (hasContent.value) {
        thinkingExpanded.value = false
      }
    }
  }
)

function toggleThinking() {
  thinkingExpanded.value = !thinkingExpanded.value
}

const imageAttachments = computed(() => props.attachments?.filter((a) => a.mime.startsWith('image/')) ?? [])
const docAttachments = computed(() => props.attachments?.filter((a) => !a.mime.startsWith('image/')) ?? [])

function fileIcon(mime: string) {
  if (mime.includes('pdf') || mime.includes('word') || mime.includes('document')) return FileText
  if (mime.includes('sheet') || mime.includes('excel') || mime.includes('csv')) return FileSpreadsheet
  if (mime.includes('presentation') || mime.includes('powerpoint')) return Presentation
  if (mime.startsWith('text/') || mime.includes('json') || mime.includes('markdown')) return FileCode
  return FileText
}

function fileSrc(a: { previewUrl?: string; remoteUrl?: string }) {
  if (a.remoteUrl) return a.remoteUrl
  return a.previewUrl ?? ''
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const copied = ref(false)
async function copy() {
  if (!props.content) return
  try {
    await navigator.clipboard.writeText(props.content)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    /* ignore */
  }
}
</script>

<template>
  <div
    :class="[
      'group flex gap-3 animate-fade-in',
      isUser ? 'flex-row-reverse' : 'flex-row'
    ]"
  >
    <!-- Avatar -->
    <div
      :class="[
        'shrink-0 size-8 rounded-full flex items-center justify-center text-white text-xs font-medium',
        isUser ? 'bg-ink-muted' : 'bg-gradient-to-br from-accent to-accent/70'
      ]"
    >
      <User v-if="isUser" class="size-4" />
      <Sparkles v-else class="size-4" />
    </div>

    <!-- Bubble -->
    <div :class="['flex-1 min-w-0 max-w-[85%]', isUser ? 'flex flex-col items-end' : '']">
      <div
        v-if="isError"
        class="flex items-start gap-2 px-4 py-3 rounded-2xl bg-danger/10 text-danger border border-danger/20 text-sm"
      >
        <AlertCircle class="size-4 mt-0.5 shrink-0" />
        <div>
          <p class="font-medium">出错了</p>
          <p class="text-xs mt-0.5 opacity-80">{{ error || '生成失败，请重试' }}</p>
        </div>
      </div>

      <div
        v-else-if="isCancelled && !isUser"
        class="rounded-2xl px-4 py-2.5 text-sm bg-surface-elevated text-ink-muted border border-border"
      >
        <div v-if="hasContent" class="markdown-body opacity-70" v-html="html" />
        <div class="flex items-center gap-1.5 text-ink-muted">
          <Ban class="size-3.5" />
          <span>{{ hasContent ? '（已中断）' : '已中断生成' }}</span>
        </div>
      </div>

      <div
        v-else-if="isAwaitingApproval"
        class="rounded-2xl px-4 py-2.5 text-sm leading-relaxed break-words bg-surface-elevated text-ink border border-border"
      >
        <div v-if="hasContent" class="markdown-body" v-html="html" />
        <div v-else class="flex items-center gap-1 text-ink-subtle text-xs">
          <Sparkles class="size-3.5" />
          <span>正在请求工具调用…</span>
        </div>
        <HitlApproval
          v-if="pendingToolCalls && pendingToolCalls.length > 0"
          :tool-calls="pendingToolCalls"
          @decide="(d) => emit('decide', d)"
        />
      </div>

      <!-- User message bubble (contains attachments + text) -->
      <div
        v-else-if="isUser"
        class="rounded-2xl px-3 py-2.5 text-sm leading-relaxed break-words bg-accent text-white max-w-full"
      >
        <div v-if="isUser && hasAttachments" class="flex flex-wrap gap-1.5 justify-end mb-2">
          <div
            v-for="img in imageAttachments"
            :key="img.id"
            class="relative rounded-lg overflow-hidden border border-white/20"
          >
            <img
              :src="fileSrc(img)"
              :alt="img.name"
              class="size-20 object-cover"
              loading="lazy"
            />
          </div>
          <div
            v-for="doc in docAttachments"
            :key="doc.id"
            class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white/15 border border-white/20 max-w-[220px]"
          >
            <component :is="fileIcon(doc.mime)" class="size-4 shrink-0 text-white/80" />
            <div class="min-w-0">
              <div class="text-xs text-white font-medium truncate">{{ doc.name }}</div>
              <div class="text-[10px] text-white/60">{{ formatSize(doc.size) }}</div>
            </div>
          </div>
        </div>
        <div v-if="content" class="whitespace-pre-wrap">{{ content }}</div>
        <div v-if="isCancelled" class="flex items-center gap-1.5 mt-1 text-white/60 text-xs">
          <Ban class="size-3.5" />
          <span>{{ content ? '（已中断）' : '已中断生成' }}</span>
        </div>
      </div>

      <!-- Assistant message bubble -->
      <div
        v-else
        class="w-full"
      >
        <!-- Thinking section -->
        <div v-if="shouldShowThinking" class="mb-2">
          <button
            @click="toggleThinking"
            class="flex items-center gap-1.5 text-xs text-ink-subtle hover:text-ink transition-colors py-1 px-1 rounded-md"
          >
            <Brain class="size-3.5" :class="{ 'animate-pulse': isActivelyThinking }" />
            <span>{{ isActivelyThinking ? '思考中…' : '已思考' }}</span>
            <ChevronDown
              class="size-3.5 transition-transform duration-200"
              :class="{ 'rotate-180': !thinkingExpanded }"
            />
          </button>
          <div
            v-show="thinkingExpanded"
            class="mt-1 pl-3 pr-3 py-2 text-xs text-ink-muted border-l-2 border-border bg-surface-muted/40 rounded-r-md"
          >
            <div v-if="hasThinkingContent" class="markdown-body thinking-body" v-html="thinkingHtml" />
            <div v-else class="flex items-center gap-1.5">
              <span class="size-1.5 rounded-full bg-ink-subtle animate-pulse-dot" />
              <span class="size-1.5 rounded-full bg-ink-subtle animate-pulse-dot" style="animation-delay: 0.2s" />
              <span class="size-1.5 rounded-full bg-ink-subtle animate-pulse-dot" style="animation-delay: 0.4s" />
              <span class="ml-1">正在分析问题、调用工具...</span>
            </div>
          </div>
        </div>

        <!-- Final answer section -->
        <div
          class="rounded-2xl px-4 py-2.5 text-sm leading-relaxed break-words bg-surface-elevated text-ink border border-border"
        >
          <div v-if="hasContent" class="markdown-body" v-html="html" />
          <span
            v-else-if="!isActivelyThinking || !shouldShowThinking"
            class="inline-flex items-center gap-1 text-ink-subtle"
          >
            <span class="size-1.5 rounded-full bg-ink-subtle animate-pulse-dot" />
            <span class="size-1.5 rounded-full bg-ink-subtle animate-pulse-dot" style="animation-delay: 0.2s" />
            <span class="size-1.5 rounded-full bg-ink-subtle animate-pulse-dot" style="animation-delay: 0.4s" />
          </span>
          <span
            v-if="isStreaming && hasContent"
            class="inline-block w-0.5 h-4 bg-ink ml-0.5 align-middle animate-pulse"
          />
        </div>
      </div>

      <!-- Artifacts (assistant generated files) -->
      <div
        v-if="!isUser && hasArtifacts && !isError && !isStreaming"
        class="w-full mt-2 space-y-2"
      >
        <div class="flex items-center gap-1.5 text-xs text-ink-subtle px-1">
          <FileCheck class="size-3.5" />
          <span>生成的文件 ({{ artifacts?.length }})</span>
        </div>
        <div class="space-y-2">
          <FileAttachment
            v-for="art in artifacts"
            :key="art.path"
            :artifact="art"
          />
        </div>
      </div>

      <!-- Actions -->
      <div
        v-if="!isUser && !isError && !isStreaming && !isAwaitingApproval && (hasContent || isCancelled || hasArtifacts)"
        :class="['flex items-center gap-1 mt-1.5 transition-opacity', isCancelled ? 'opacity-100' : 'opacity-0 group-hover:opacity-100']"
      >
        <button
          v-if="hasContent"
          class="p-1.5 rounded-md text-ink-subtle hover:text-ink hover:bg-surface-muted"
          :aria-label="copied ? '已复制' : '复制'"
          @click="copy"
        >
          <Check v-if="copied" class="size-3.5" />
          <Copy v-else class="size-3.5" />
        </button>
        <button
          v-if="canRegenerate || isCancelled"
          class="p-1.5 rounded-md text-ink-subtle hover:text-ink hover:bg-surface-muted"
          aria-label="重新生成"
          @click="emit('regenerate')"
        >
          <RefreshCw class="size-3.5" />
        </button>
      </div>
    </div>
  </div>
</template>

<style>
.markdown-body {
  line-height: 1.65;
  word-wrap: break-word;
}
.markdown-body p {
  margin: 0.4em 0;
}
.markdown-body p:first-child {
  margin-top: 0;
}
.markdown-body p:last-child {
  margin-bottom: 0;
}
.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  font-weight: 600;
  line-height: 1.3;
  margin: 0.9em 0 0.4em;
}
.markdown-body h1 { font-size: 1.4em; }
.markdown-body h2 { font-size: 1.2em; }
.markdown-body h3 { font-size: 1.05em; }
.markdown-body h4 { font-size: 1em; }
.markdown-body ul,
.markdown-body ol {
  margin: 0.4em 0;
  padding-left: 1.4em;
}
.markdown-body li {
  margin: 0.15em 0;
}
.markdown-body li > p {
  margin: 0.15em 0;
}
.markdown-body code {
  font-family: var(--default-mono-font-family, ui-monospace, SFMono-Regular, monospace);
  font-size: 0.875em;
  background: rgb(var(--surface-muted));
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
.markdown-body pre {
  margin: 0.6em 0;
  padding: 0;
  border-radius: 8px;
  overflow: hidden;
  background: rgb(var(--surface-muted));
  border: 1px solid rgb(var(--border));
}
.markdown-body pre code {
  display: block;
  background: transparent;
  padding: 0.85em 1em;
  font-size: 0.85em;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
}
.markdown-body pre.shiki-fallback {
  color: rgb(var(--ink));
}
.markdown-body blockquote {
  margin: 0.6em 0;
  padding: 0.2em 0.8em;
  border-left: 3px solid rgb(var(--border-strong));
  color: rgb(var(--ink-muted));
}
.markdown-body table {
  border-collapse: collapse;
  margin: 0.6em 0;
  font-size: 0.9em;
}
.markdown-body th,
.markdown-body td {
  border: 1px solid rgb(var(--border));
  padding: 0.4em 0.6em;
}
.markdown-body th {
  background: rgb(var(--surface-muted));
  font-weight: 600;
}
.markdown-body a {
  color: rgb(var(--accent));
  text-decoration: underline;
  text-underline-offset: 2px;
}
.markdown-body hr {
  border: none;
  border-top: 1px solid rgb(var(--border));
  margin: 1em 0;
}
.thinking-body {
  opacity: 0.8;
  font-style: italic;
}
.thinking-body p {
  margin: 0.3em 0;
}
.thinking-body code {
  font-size: 0.9em;
  opacity: 0.9;
}
</style>
