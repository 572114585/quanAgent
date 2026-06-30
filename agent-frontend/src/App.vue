<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
</script>

<template>
  <AppShell>
    <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-2 focus:rounded-md focus:bg-surface focus:text-ink focus:shadow-lg focus:border focus:border-border"
    >
      跳到主内容
    </a>
    <div id="main-content" class="h-full">
      <RouterView v-slot="{ Component, route }">
        <transition name="fade" mode="out-in">
          <component :is="Component" :key="route.fullPath" />
        </transition>
      </RouterView>
    </div>
  </AppShell>
</template>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
