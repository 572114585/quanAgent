/**
 * usePlatform — detects runtime environment (web vs Tauri) and
 * exposes feature flags so the UI can adapt to mobile vs desktop.
 */
import { computed, onMounted, ref } from 'vue'

export type Platform = 'web' | 'tauri'
export type OS = 'macos' | 'ios' | 'android' | 'windows' | 'linux' | 'unknown'

const platform = ref<Platform>('web')
const os = ref<OS>('unknown')
const isMobile = computed(() => os.value === 'ios' || os.value === 'android')

async function detect() {
  // Tauri injects a global at runtime
  const inTauri =
    typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
  platform.value = inTauri ? 'tauri' : 'web'

  if (inTauri) {
    try {
      const osModule = await import('@tauri-apps/plugin-os')
      const t = await osModule.type()
      os.value = (t as OS) ?? 'unknown'
    } catch {
      os.value = 'unknown'
    }
  } else if (typeof navigator !== 'undefined') {
    const ua = navigator.userAgent.toLowerCase()
    if (/iphone|ipad|ipod/.test(ua)) os.value = 'ios'
    else if (/android/.test(ua)) os.value = 'android'
    else if (/mac/.test(ua)) os.value = 'macos'
    else if (/win/.test(ua)) os.value = 'windows'
    else if (/linux/.test(ua)) os.value = 'linux'
    else os.value = 'unknown'
  }
}

export function usePlatform() {
  onMounted(detect)
  return { platform, os, isMobile }
}
