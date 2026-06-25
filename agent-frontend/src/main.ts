import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { useTheme } from './composables/useTheme'
import { useSettingsStore } from './stores/settings'
import { setRuntimeBaseUrl } from './api/sse'
import './styles/global.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

useTheme().applyInitial()

const settings = useSettingsStore()
setRuntimeBaseUrl(settings.apiBaseUrl)

app.mount('#app')
