/**
 * useShortcuts — registers global keyboard shortcuts.
 * macOS uses Cmd, others use Ctrl. Skip when focus is in an input
 * unless explicitly allowed.
 */
import { onBeforeUnmount, onMounted } from 'vue'

export interface Shortcut {
  /** e.g. 'mod+k', 'mod+/', 'escape' */
  combo: string
  description: string
  /** When true, fires even while typing in an input. */
  allowInInputs?: boolean
  handler: (e: KeyboardEvent) => void
}

const isMac =
  typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform)

function normalize(combo: string): string {
  return combo
    .toLowerCase()
    .split('+')
    .map((p) => p.trim())
    .sort()
    .join('+')
}

function eventToCombo(e: KeyboardEvent): string {
  const parts: string[] = []
  if (e.metaKey || (isMac && e.ctrlKey)) parts.push('mod')
  else if (e.ctrlKey) parts.push('mod')
  if (e.altKey) parts.push('alt')
  if (e.shiftKey) parts.push('shift')
  const k = e.key.toLowerCase()
  if (!['control', 'meta', 'alt', 'shift'].includes(k)) parts.push(k)
  return parts.sort().join('+')
}

function isTextInput(el: EventTarget | null) {
  if (!(el instanceof HTMLElement)) return false
  const tag = el.tagName
  return (
    tag === 'INPUT' ||
    tag === 'TEXTAREA' ||
    tag === 'SELECT' ||
    el.isContentEditable
  )
}

export function useShortcuts(shortcuts: Shortcut[]) {
  const normalized = shortcuts.map((s) => ({ ...s, _combo: normalize(s.combo) }))

  function onKeyDown(e: KeyboardEvent) {
    if (!(e instanceof KeyboardEvent)) return
    const inInput = isTextInput(e.target)
    const combo = eventToCombo(e)
    for (const s of normalized) {
      if (s._combo !== combo) continue
      if (inInput && !s.allowInInputs) continue
      e.preventDefault()
      s.handler(e)
      return
    }
  }

  onMounted(() => window.addEventListener('keydown', onKeyDown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))
}
