/**
 * useMarkdown — marked + shiki Markdown renderer.
 * shiki is loaded lazily via shiki/core + onig to keep the initial bundle small.
 * The highlighter caches a small set of common languages.
 */
import { Marked } from 'marked'
import { computed, ref, watch, type Ref } from 'vue'
import { useTheme } from './useTheme'

let highlighterPromise: Promise<any> | null = null
let markedInstance: Marked | null = null

function getMarked(): Marked {
  if (!markedInstance) {
    markedInstance = new Marked({
      gfm: true,
      breaks: true
    })
    markedInstance.use({
      renderer: {
        code({ text, lang }: { text: string; lang?: string }) {
          const langStr = (lang || '').trim().split(/\s+/)[0] || 'text'
          const code = escapeHtml(text)
          return `<pre class="shiki-fallback" data-lang="${langStr}"><code>${code}</code></pre>`
        }
      }
    })
  }
  return markedInstance
}

async function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = (async () => {
      const { createHighlighterCore } = await import('shiki/core')
      const { createOnigurumaEngine } = await import('shiki/engine/oniguruma')
      return createHighlighterCore({
        themes: [
          import('shiki/themes/github-light.mjs'),
          import('shiki/themes/github-dark.mjs')
        ],
        langs: [
          import('shiki/langs/javascript.mjs'),
          import('shiki/langs/typescript.mjs'),
          import('shiki/langs/vue.mjs'),
          import('shiki/langs/json.mjs'),
          import('shiki/langs/html.mjs'),
          import('shiki/langs/css.mjs'),
          import('shiki/langs/bash.mjs'),
          import('shiki/langs/python.mjs'),
          import('shiki/langs/go.mjs'),
          import('shiki/langs/rust.mjs'),
          import('shiki/langs/java.mjs'),
          import('shiki/langs/markdown.mjs'),
          import('shiki/langs/yaml.mjs'),
          import('shiki/langs/sql.mjs'),
          import('shiki/langs/diff.mjs')
        ],
        engine: createOnigurumaEngine(
          import('@shikijs/engine-oniguruma/wasm-inlined')
        )
      })
    })()
  }
  return highlighterPromise
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function useMarkdown(source: Ref<string>) {
  const html = ref('')
  const { resolved } = useTheme()
  const renderer = getMarked()

  let renderVersion = 0

  async function render() {
    const myVersion = ++renderVersion
    const raw = source.value || ''
    const out = await renderer.parse(raw)
    if (myVersion !== renderVersion) return
    let result = String(out)

    if (result.includes('shiki-fallback')) {
      try {
        const hl = await getHighlighter()
        if (myVersion !== renderVersion) return
        const theme = resolved.value === 'dark' ? 'github-dark' : 'github-light'
        result = result.replace(
          /<pre class="shiki-fallback" data-lang="([^"]*)"><code>([\s\S]*?)<\/code><\/pre>/g,
          (_match, lang: string, code: string) => {
            const decoded = code
              .replace(/&amp;/g, '&')
              .replace(/&lt;/g, '<')
              .replace(/&gt;/g, '>')
              .replace(/&quot;/g, '"')
              .replace(/&#39;/g, "'")
            const supported = hl.getLoadedLanguages() as string[]
            const finalLang = supported.includes(lang) ? lang : 'text'
            try {
              return hl.codeToHtml(decoded, { lang: finalLang, theme })
            } catch {
              return `<pre class="shiki-fallback"><code>${code}</code></pre>`
            }
          }
        )
      } catch {
        // shiki not available, keep the escaped fallback
      }
    }

    if (myVersion === renderVersion) {
      html.value = result
    }
  }

  watch(source, () => {
    void render()
  }, { immediate: true })

  return { html: computed(() => html.value) }
}
