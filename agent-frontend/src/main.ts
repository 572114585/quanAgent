import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { useTheme } from '@/composables/useTheme'
import { useSettingsStore } from '@/stores/settings'
import { useSessionsStore } from '@/stores/sessions'
import './styles/global.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// 启动前加载持久化数据，避免组件读到空状态闪烁。
// 顺序：主题（减 FOUC）→ settings（含 setRuntimeBaseUrl）→ sessions（列表）。
// settings.load() 内部会把持久化的 apiBaseUrl 应用到 runtimeBaseUrl，修复原 S3 bug。
//
// 用 async IIFE 包裹而非 top-level await：vite 默认 build target（safari13 / chrome105）
// 中前者不支持 top-level await；IIFE 形式兼容所有目标，挂载延迟在毫秒级，无 FOUC。
void (async () => {
  await useTheme().applyInitial()
  const settings = useSettingsStore()
  await settings.load()
  const sessions = useSessionsStore()
  await sessions.load()
  app.mount('#app')
})()
