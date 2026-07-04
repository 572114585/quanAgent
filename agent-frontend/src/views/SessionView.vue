<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useChatStore } from '@/stores/chat'
import ChatPanel from '@/components/chat/ChatPanel.vue'

const props = defineProps<{ id: string }>()
const sessions = useSessionsStore()
const chat = useChatStore()
const session = computed(() => sessions.list.find((s) => s.id === props.id))

onMounted(() => {
  sessions.activate(props.id)
  void chat.loadHistory(props.id)
})
watch(
  () => props.id,
  (id) => {
    sessions.activate(id)
    void chat.loadHistory(id)
  }
)
</script>

<template>
  <div v-if="session" class="h-full flex flex-col">
    <ChatPanel :session="session" class="flex-1" />
  </div>
  <div v-else class="flex-1 flex items-center justify-center text-ink-subtle">
    会话不存在或已被删除。
  </div>
</template>
