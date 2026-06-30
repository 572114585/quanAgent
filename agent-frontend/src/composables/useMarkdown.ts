/**
 * useMarkdown — marked + shiki Markdown renderer.
 * shiki is loaded lazily via shiki/core + onig to keep the initial bundle small.
 * The highlighter caches a small set of common languages.
 */
import { Marked } from 'marked'
import DOMPurify, { type Config } from 'dompurify'
import { computed, ref, watch, type Ref } from 'vue'
import type { HighlighterCore } from 'shiki/core'
import { useTheme } from './useTheme'

let highlighterPromise: Promise<HighlighterCore> | null = null
let markedInstance: Marked | null = null

/**
 * DOMPurify 配置：保留 shiki 输出所需的 data-lang / style / tabindex，
 * 其余按默认策略（移除 script/iframe/on* 事件/javascript: 协议等）。
 */
const SANITIZE_CONFIG: Config = {
  ADD_ATTR: ['data-lang', 'style', 'tabindex'],
  ALLOW_DATA_ATTR: true
}

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
          return `<pre class="shiki-fallback" data-lang="${escapeHtml(langStr)}"><code>${code}</code></pre>`
        }
      }
    })
  }
  return markedInstance
}

function getHighlighter(): Promise<HighlighterCore> {
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
  // if 块内已确保赋值，但模块级 let 变量 TS 不做 narrowing，显式断言非空
  return highlighterPromise!
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
            // 解码顺序：&amp; 必须最后还原，避免双重解码
            // （原文 &lt; → escapeHtml 后 &amp;lt; → 若先 &amp; 得 &lt; → 再 &lt; 得 <，错误）
            const decoded = code
              .replace(/&lt;/g, '<')
              .replace(/&gt;/g, '>')
              .replace(/&quot;/g, '"')
              .replace(/&#39;/g, "'")
              .replace(/&amp;/g, '&')
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
      // XSS 防护最后一道闸：marked v14 已移除内置 sanitize，
      // LLM 输出可能被提示注入污染（<script> / <img onerror> / javascript: 等），
      // 在 v-html 渲染前必须净化。Tauri WebView 同源下可调用后端能力，风险被放大。
      // 未设 RETURN_TRUSTED_TYPE: true，匹配返回 string 的重载，无需断言。
      html.value = DOMPurify.sanitize(result, SANITIZE_CONFIG)
    }
  }

  watch(source, () => {
    void render()
  }, { immediate: true })

  return { html: computed(() => html.value) }
}
