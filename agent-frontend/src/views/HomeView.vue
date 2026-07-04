<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import { useSessionsStore } from '@/stores/sessions'
import { useChatStore } from '@/stores/chat'

const sessions = useSessionsStore()
const chat = useChatStore()
const router = useRouter()
const session = computed(() => sessions.active)

/** 与 SessionView 行为一致：进入/切换 active 会话时拉取历史消息。 */
function loadActiveHistory(id: string | null) {
  if (id) void chat.loadHistory(id)
}

onMounted(() => loadActiveHistory(sessions.activeId))
watch(
  () => sessions.activeId,
  (id) => loadActiveHistory(id)
)

function newChat() {
  const s = sessions.create()
  router.push({ name: 'session', params: { id: s.id } })
}
</script>

<template>
  <div class="h-full flex flex-col">
    <div v-if="!session" class="flex-1 flex items-center justify-center px-6">
      <div class="max-w-md text-center space-y-3 animate-fade-in">
        <h1 class="text-2xl font-semibold text-ink">开始与 Agent 对话</h1>
        <p class="text-sm text-ink-muted leading-relaxed">
          左侧选择一个历史会话，或点击「新建对话」开始一次全新的交互。
        </p>
        <button class="btn-primary" @click="newChat">新建对话</button>
      </div>
    </div>

    <ChatPanel v-else :session="session" class="flex-1" />
  </div>
</template>
