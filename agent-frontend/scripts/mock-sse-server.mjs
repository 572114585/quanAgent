#!/usr/bin/env node
/**
 * Mock SSE 服务 —— 仅用于前端 Phase 3 联调验收。
 *
 * 启动： node scripts/mock-sse-server.mjs   或   npm run mock:sse
 * 端口： 8787
 *
 * 协议：
 *  - POST /chat     接收 JSON ChatRequest，返回 text/event-stream
 *  - GET  /health   健康检查
 *
 * 流式格式（与 src/types/domain.ts 的 StreamEvent 对齐）：
 *   data: {"type":"start","messageId":"..."}
 *   data: {"type":"delta","delta":"一段文字"}
 *   ...
 *   data: {"type":"usage","promptTokens":12,"completionTokens":34}
 *   data: {"type":"done","messageId":"..."}
 */
import http from 'node:http'
import { randomUUID } from 'node:crypto'

const PORT = Number(process.env.MOCK_SSE_PORT || 8787)

/** 把内容切成 3~5 段，每段约 80~150ms 推送一次。 */
function buildSegments(userText) {
  const safe = (userText || '').toString().replace(/[<>]/g, '')
  const preview = safe.length > 24 ? safe.slice(0, 24) + '…' : safe
  const full = [
    `# 你好，我是 mock agent

我收到了你的消息：\`${preview}\`。下面是一段带 **Markdown** 的示例回复，用于验证流式渲染。`,
    `

## 我能做的事

- 逐字流式输出（打字机效果）
- 渲染 **加粗**、*斜体*、\`内联代码\`
- 渲染代码块、表格、列表

`,
    `### 代码块示例

\`\`\`ts
import { ref } from 'vue'

const count = ref(0)
function inc() {
  count.value++
}
\`\`\`

`,
    `### 简单表格

| 能力        | 状态 |
| ----------- | ---- |
| SSE 流式    | ✅   |
| 取消 / stop | ✅   |
| Markdown    | ✅   |
| 错误重试    | ✅   |

`,
    `---

如果以上都正常，说明前端 Phase 3 集成完成。`
  ]
  return full
}

function sse(res, event) {
  res.write(`data: ${JSON.stringify(event)}\n\n`)
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = []
    req.on('data', (c) => chunks.push(c))
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf-8')
      if (!raw) return resolve({})
      try {
        resolve(JSON.parse(raw))
      } catch (e) {
        reject(e)
      }
    })
    req.on('error', reject)
  })
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

function randInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

const server = http.createServer(async (req, res) => {
  const url = req.url || '/'

  // CORS 预检 & 通用头，方便浏览器/Tauri 直接调用
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Accept')
  if (req.method === 'OPTIONS') {
    res.writeHead(204)
    res.end()
    return
  }

  if (url === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ ok: true, ts: Date.now() }))
    return
  }

  if (url === '/chat' && req.method === 'POST') {
    let body
    try {
      body = await readBody(req)
    } catch (e) {
      res.writeHead(400, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ message: 'invalid json body' }))
      return
    }

    const messageId = randomUUID()
    const sessionId = body?.sessionId || randomUUID()
    const segments = buildSegments(body?.message || '')

    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no'
    })

    sse(res, { type: 'start', messageId })

    let aborted = false
    req.on('close', () => {
      aborted = true
    })

    let totalBytes = 0
    for (let i = 0; i < segments.length; i++) {
      if (aborted) break
      const chunk = segments[i]
      sse(res, { type: 'delta', delta: chunk })
      totalBytes += Buffer.byteLength(chunk, 'utf-8')
      const wait = randInt(80, 150)
      await sleep(wait)
    }

    if (!aborted) {
      sse(res, {
        type: 'usage',
        promptTokens: Math.ceil((body?.message?.length || 0) / 2),
        completionTokens: Math.ceil(totalBytes / 2)
      })
      sse(res, { type: 'done', messageId })
    }

    res.end()
    const preview = String(body?.message || '').slice(0, 40)
    console.log(
      `[mock-sse] session=${sessionId} msg="${preview}" bytes=${totalBytes}`
    )
    return
  }

  res.writeHead(404, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify({ message: 'not found' }))
})

server.listen(PORT, () => {
  console.log(`[mock-sse] listening on http://localhost:${PORT}`)
  console.log('[mock-sse] try: curl -X POST http://localhost:8787/chat -H "Content-Type: application/json" -d "{\\"message\\":\\"hi\\"}"')
})
