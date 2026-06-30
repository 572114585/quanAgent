import { createRouter, createWebHistory } from 'vue-router'
import { useSessionsStore } from '@/stores/sessions'

export const router = createRouter({
  // base 与 vite 的 BASE_URL 对齐，避免 Tauri 自定义协议下刷新 404
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue')
    },
    {
      path: '/session/:id',
      name: 'session',
      component: () => import('@/views/SessionView.vue'),
      props: true
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue')
    },
    // 未知路由重定向到首页，避免白屏
    {
      path: '/:pathMatch(.*)*',
      redirect: { name: 'home' }
    }
  ],
  scrollBehavior(_to, _from, savedPosition) {
    // 浏览器后退/前进时恢复滚动位置
    if (savedPosition) return savedPosition
    return { top: 0 }
  }
})

// 防御性守卫：确保 sessions 已加载
// （main.ts 已 await，这里仅在异常/直接路由进入时兜底）
router.beforeEach(async () => {
  const sessions = useSessionsStore()
  if (!sessions.isLoaded) await sessions.load()
})
