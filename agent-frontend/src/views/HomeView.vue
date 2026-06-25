<script setup lang="ts">
import { computed } from 'vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import { useSessionsStore } from '@/stores/sessions'

const sessions = useSessionsStore()
const session = computed(() => sessions.active)
</script>

<template>
  <div class="h-full flex flex-col">
    <div v-if="!session" class="flex-1 flex items-center justify-center px-6">
      <div class="max-w-md text-center space-y-3 animate-fade-in">
        <h1 class="text-2xl font-semibold text-ink">开始与 Agent 对话</h1>
        <p class="text-sm text-ink-muted leading-relaxed">
          左侧选择一个历史会话，或点击「新建对话」开始一次全新的交互。
        </p>
        <button class="btn-primary" @click="sessions.create()">新建对话</button>
      </div>
    </div>

    <ChatPanel v-else :session="session" class="flex-1" />
  </div>
</template>
