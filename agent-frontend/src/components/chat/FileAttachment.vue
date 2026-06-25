<script setup lang="ts">
import { computed, ref } from 'vue'
import { FileText, FileSpreadsheet, File, Download, Eye, X, ExternalLink } from 'lucide-vue-next'
import type { ArtifactFile } from '@/types/domain'
import { getRuntimeBaseUrl } from '@/api/sse'

const props = defineProps<{
  artifact: ArtifactFile
}>()

const previewOpen = ref(false)
const previewError = ref(false)

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

const fileColor = computed(() => {
  const ext = fileExt.value
  if (ext === 'pdf') return 'text-red-500 bg-red-50'
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'text-green-600 bg-green-50'
  if (['docx', 'doc'].includes(ext)) return 'text-blue-600 bg-blue-50'
  if (['pptx', 'ppt'].includes(ext)) return 'text-orange-600 bg-orange-50'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) return 'text-purple-600 bg-purple-50'
  return 'text-ink-muted bg-surface-muted'
})

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

const fullUrl = computed(() => {
  const base = getRuntimeBaseUrl()
  const url = props.artifact.url
  if (!base) return url
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${base.replace(/\/+$/, '')}${url.startsWith('/') ? url : '/' + url}`
})

function openPreview() {
  previewError.value = false
  previewOpen.value = true
}

function closePreview() {
  previewOpen.value = false
}

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
        <component :is="FileIcon" class="size-5" />
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium text-ink truncate" :title="artifact.name">{{ artifact.name }}</p>
        <p class="text-xs text-ink-subtle mt-0.5">{{ fileSizeLabel }} · {{ artifact.mime }}</p>
      </div>
      <div class="flex items-center gap-1 shrink-0">
        <button
          v-if="canPreview"
          class="p-1.5 rounded-md text-ink-subtle hover:text-accent hover:bg-accent/10 transition-colors"
          aria-label="预览"
          title="预览"
          @click="openPreview"
        >
          <Eye class="size-4" />
        </button>
        <a
          :href="fullUrl"
          :download="artifact.name"
          target="_blank"
          rel="noopener"
          class="p-1.5 rounded-md text-ink-subtle hover:text-accent hover:bg-accent/10 transition-colors"
          aria-label="下载"
          title="下载"
        >
          <Download class="size-4" />
        </a>
      </div>
    </div>

    <!-- 图片缩略图 -->
    <div v-if="isImage" class="mt-2">
      <img
        :src="fullUrl"
        :alt="artifact.name"
        class="max-w-full max-h-64 rounded-lg border border-border object-contain cursor-pointer hover:opacity-90 transition-opacity"
        @click="openPreview"
      />
    </div>

    <!-- 预览弹窗 -->
    <Teleport to="body">
      <div
        v-if="previewOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
        @click.self="closePreview"
      >
        <div class="relative w-[90vw] h-[90vh] max-w-5xl bg-surface rounded-2xl shadow-2xl flex flex-col overflow-hidden">
          <div class="flex items-center justify-between px-4 py-3 border-b border-border">
            <div class="flex items-center gap-2 min-w-0">
              <component :is="FileIcon" :class="['size-4', fileColor.split(' ')[0]]" />
              <span class="text-sm font-medium text-ink truncate">{{ artifact.name }}</span>
            </div>
            <div class="flex items-center gap-2">
              <a
                :href="fullUrl"
                :download="artifact.name"
                target="_blank"
                rel="noopener"
                class="flex items-center gap-1 px-3 py-1.5 text-xs rounded-md text-ink-muted hover:text-accent hover:bg-accent/10 transition-colors"
              >
                <ExternalLink class="size-3.5" />
                新窗口打开
              </a>
              <button
                class="p-1.5 rounded-md text-ink-subtle hover:text-ink hover:bg-surface-muted transition-colors"
                aria-label="关闭"
                @click="closePreview"
              >
                <X class="size-5" />
              </button>
            </div>
          </div>
          <div class="flex-1 overflow-auto bg-surface-muted/30 flex items-center justify-center">
            <template v-if="isImage">
              <img
                :src="fullUrl"
                :alt="artifact.name"
                class="max-w-full max-h-full object-contain"
                @error="handlePreviewError"
              />
            </template>
            <template v-else-if="fileExt === 'pdf'">
              <iframe
                v-if="!previewError"
                :src="fullUrl"
                class="w-full h-full border-0"
                :title="artifact.name"
                @error="handlePreviewError"
              />
              <div v-else class="text-center text-ink-muted p-8">
                <FileText class="size-12 mx-auto mb-3 opacity-50" />
                <p class="text-sm">无法内嵌预览 PDF，请点击右上角"新窗口打开"或下载查看</p>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
