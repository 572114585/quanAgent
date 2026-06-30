<script setup lang="ts">
import { computed, ref, watch, nextTick, onScopeDispose, useTemplateRef } from 'vue'
import { FileText, FileSpreadsheet, File, Download, Eye, X, ExternalLink } from 'lucide-vue-next'
import type { ArtifactFile } from '@/types/domain'
import { getRuntimeBaseUrl } from '@/api/sse'

const props = defineProps<{
  artifact: ArtifactFile
}>()

const previewOpen = ref(false)
const previewError = ref(false)

const dialogRef = useTemplateRef<HTMLElement>('dialogRef')
const closeBtnRef = useTemplateRef<HTMLElement>('closeBtnRef')
let previouslyFocused: HTMLElement | null = null

const fileExt = computed(() => {
  const name = props.artifact.name
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
})

const fileSizeLabel = computed(() => {
  const size = props.artifact.size
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
})

// 改用语义色，暗色模式自动适配（替换原硬编码 bg-red-50 等）
const fileColor = computed(() => {
  const ext = fileExt.value
  if (ext === 'pdf') return 'text-danger bg-danger/10'
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'text-success bg-success/10'
  if (['docx', 'doc'].includes(ext)) return 'text-accent bg-accent/10'
  if (['pptx', 'ppt'].includes(ext)) return 'text-warning bg-warning/10'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) return 'text-accent bg-accent/10'
  return 'text-ink-muted bg-surface-muted'
})

const fileIconColor = computed(() => fileColor.value.split(' ')[0])

const FileIcon = computed(() => {
  const ext = fileExt.value
  if (ext === 'pdf') return FileText
  if (['xlsx', 'xls', 'csv'].includes(ext)) return FileSpreadsheet
  if (['docx', 'doc'].includes(ext)) return FileText
  return File
})

const canPreview = computed(() => {
  const ext = fileExt.value
  return ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)
})

const isImage = computed(() => {
  return ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(fileExt.value)
})

/**
 * URL scheme 白名单校验，防止 javascript:/data:text/html 等危险协议
 * 经 <a> / <img> / <iframe> 渲染时触发脚本或伪冒内容。
 * - 相对路径（/开头且非 //）放行
 * - http/https 放行
 * - data:image/* 放行（图片内联）
 */
function isSafeUrl(url: string): boolean {
  if (!url) return false
  if (url.startsWith('/') && !url.startsWith('//')) return true
  if (url.startsWith('http://') || url.startsWith('https://')) return true
  if (url.startsWith('data:image/')) return true
  return false
}

const fullUrl = computed(() => {
  const url = props.artifact.url
  if (!isSafeUrl(url)) return ''
  const base = getRuntimeBaseUrl()
  if (!base) return url
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) return url
  return `${base.replace(/\/+$/, '')}${url.startsWith('/') ? url : '/' + url}`
})

/** 焦点陷阱：Tab 在弹窗内循环。 */
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    closePreview()
    return
  }
  if (e.key === 'Tab' && dialogRef.value) {
    const focusables = dialogRef.value.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
    if (focusables.length === 0) return
    const first = focusables[0]
    const last = focusables[focusables.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }
}

function openPreview() {
  previewError.value = false
  previouslyFocused = document.activeElement as HTMLElement
  previewOpen.value = true
}

function closePreview() {
  previewOpen.value = false
}

// 打开时聚焦关闭按钮、注册键盘监听；关闭时还原焦点
watch(previewOpen, (open) => {
  if (open) {
    nextTick(() => closeBtnRef.value?.focus())
    document.addEventListener('keydown', onKeydown)
  } else {
    document.removeEventListener('keydown', onKeydown)
    previouslyFocused?.focus?.()
    previouslyFocused = null
  }
})

onScopeDispose(() => {
  document.removeEventListener('keydown', onKeydown)
})

function handlePreviewError() {
  previewError.value = true
}
</script>

<template>
  <div class="file-attachment">
    <div
      class="flex items-center gap-3 px-3 py-2.5 rounded-xl border border-border bg-surface hover:border-border-strong transition-colors group"
    >
      <div :class="['shrink-0 size-10 rounded-lg flex items-center justify-center', fileColor]">
        <component :is="FileIcon" class="size-5" aria-hidden="true" />
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium text-ink truncate" :title="artifact.name">{{ artifact.name }}</p>
        <p class="text-xs text-ink-muted mt-0.5">{{ fileSizeLabel }} · {{ artifact.mime }}</p>
      </div>
      <div class="flex items-center gap-1 shrink-0">
        <button
          v-if="canPreview"
          class="p-1.5 rounded-md text-ink-muted hover:text-accent hover:bg-accent/10 transition-colors"
          aria-label="预览"
          title="预览"
          @click="openPreview"
        >
          <Eye class="size-4" aria-hidden="true" />
        </button>
        <a
          v-if="fullUrl"
          :href="fullUrl"
          :download="artifact.name"
          target="_blank"
          rel="noopener noreferrer"
          class="p-1.5 rounded-md text-ink-muted hover:text-accent hover:bg-accent/10 transition-colors"
          aria-label="下载"
          title="下载"
        >
          <Download class="size-4" aria-hidden="true" />
        </a>
      </div>
    </div>

    <!-- 图片缩略图 -->
    <div v-if="isImage && fullUrl" class="mt-2">
      <img
        :src="fullUrl"
        :alt="artifact.name"
        loading="lazy"
        class="max-w-full max-h-64 rounded-lg border border-border object-contain cursor-pointer hover:opacity-90 transition-opacity"
        @click="openPreview"
      />
    </div>

    <!-- 预览弹窗 -->
    <Teleport to="body">
      <div
        v-if="previewOpen"
        ref="dialogRef"
        role="dialog"
        aria-modal="true"
        :aria-label="`预览 ${artifact.name}`"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
        @click.self="closePreview"
      >
        <div class="relative w-[90vw] h-[90vh] max-w-5xl bg-surface rounded-2xl shadow-2xl flex flex-col overflow-hidden">
          <div class="flex items-center justify-between px-4 py-3 border-b border-border">
            <div class="flex items-center gap-2 min-w-0">
              <component :is="FileIcon" :class="['size-4', fileIconColor]" aria-hidden="true" />
              <span class="text-sm font-medium text-ink truncate">{{ artifact.name }}</span>
            </div>
            <div class="flex items-center gap-2">
              <a
                v-if="fullUrl"
                :href="fullUrl"
                :download="artifact.name"
                target="_blank"
                rel="noopener noreferrer"
                class="flex items-center gap-1 px-3 py-1.5 text-xs rounded-md text-ink-muted hover:text-accent hover:bg-accent/10 transition-colors"
              >
                <ExternalLink class="size-3.5" aria-hidden="true" />
                新窗口打开
              </a>
              <button
                ref="closeBtnRef"
                class="p-1.5 rounded-md text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors"
                aria-label="关闭预览"
                @click="closePreview"
              >
                <X class="size-5" aria-hidden="true" />
              </button>
            </div>
          </div>
          <div class="flex-1 overflow-auto bg-surface-muted/30 flex items-center justify-center">
            <template v-if="isImage">
              <img
                v-if="fullUrl"
                :src="fullUrl"
                :alt="artifact.name"
                class="max-w-full max-h-full object-contain"
                @error="handlePreviewError"
              />
              <div v-else class="text-center text-ink-muted p-8">
                <FileText class="size-12 mx-auto mb-3 opacity-50" aria-hidden="true" />
                <p class="text-sm">图片地址不安全，无法预览</p>
              </div>
            </template>
            <template v-else-if="fileExt === 'pdf'">
              <iframe
                v-if="!previewError && fullUrl"
                :src="fullUrl"
                sandbox="allow-same-origin"
                referrerpolicy="no-referrer"
                class="w-full h-full border-0"
                :title="`预览 ${artifact.name}`"
                @error="handlePreviewError"
              />
              <div v-else class="text-center text-ink-muted p-8">
                <FileText class="size-12 mx-auto mb-3 opacity-50" aria-hidden="true" />
                <p class="text-sm">无法内嵌预览 PDF，请点击右上角"新窗口打开"或下载查看</p>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>