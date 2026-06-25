<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import ChatPanel from '@/components/chat/ChatPanel.vue'

const props = defineProps<{ id: string }>()
const sessions = useSessionsStore()
const session = computed(() => sessions.list.find((s) => s.id === props.id))

onMounted(() => sessions.activate(props.id))
watch(
  () => props.id,
  (id) => sessions.activate(id)
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
