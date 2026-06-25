import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
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
    }
  ],
  scrollBehavior() {
    return { top: 0 }
  }
})
