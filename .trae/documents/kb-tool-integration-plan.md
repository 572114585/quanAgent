# 知识库工具(kb_tool)接入 deepagent 方案

## 概述

借鉴 WeKnora 的 RAG 设计(BM25 + Dense + RRF 融合 + 父子分块),用纯 Python 实现一个自包含的知识库工具 `kb_search`,挂载到现有 `research_subagent`,与 `web_search` 并列。文档解析复用 MinerU(命令行子进程),输出 Markdown 后按章节做父子分块。Embedding 双模式(本地 BGE 默认 / OpenAI 兼容 API),通过 env 开关切换。前端零改动,复用现有 toolCalls 渲染。

## 当前状态分析(基于实际探索)

### 已确认的事实

1. **工具注册模式**:LangChain `@tool` 装饰器 + 函数 + 类型注解 + docstring。参考 [web_search.py](file:///d:/project/tools/web_search.py)
2. **async 模式**:同步 `@tool` 函数体内用 `asyncio.run(_run())` 跑 async 逻辑(LangChain astream 在独立线程调 sync tool,当前线程无事件循环)。见 [web_search.py L121-149](file:///d:/project/tools/web_search.py#L121-L149)
3. **research_subagent 现状**:[prompts.py L24-39](file:///d:/project/agent_core/prompts.py#L24-L39),`tools=[web_search]`,system_prompt 引导"用 web_search 检索"
4. **配置模式**:[config.py](file:///d:/project/agent_core/config.py) 模块级 `os.getenv(...)` 常量,无类
5. **SSE 层无需改动**:任何 `@tool` 被调用时,`entrypoints/web.py` 的 `_stream_agent` 自动产生 `tool_call` + `tool_result` 事件,前端 `MessageBubble.vue` 思考区通用工具卡片自动渲染
6. **错误处理约定**:`try/except` 全捕获,返回中文 str,不 raise。见 [web_search.py L150](file:///d:/project/tools/web_search.py#L150)

### 用户决策

- **Embedding**:两者都支持,默认本地 BGE-small-zh-v1.5,通过 `EMBEDDING_PROVIDER` env 切换
- **工具挂载**:仅 research_subagent 用,与 web_search 并列

## 改动清单

### 新建文件(2 个)

#### 1. `d:\project\tools\kb_tool.py`(核心,约 350 行)

**职责**:实现 KnowledgeBase 类 + `@tool kb_search` 函数 + `@tool kb_add_document` 函数

**结构**:

```python
# tools/kb_tool.py
"""自包含知识库工具,设计参考 WeKnora,纯 Python 实现。
- 文档解析:MinerU(子进程)→ Markdown
- 分块:Markdown H2 章节感知 + 段落滑窗,父子结构
- 检索:BM25(rank_bm25) + Dense(Chroma) + RRF 融合
- Embedding:本地 BGE-small-zh(默认) / OpenAI 兼容 API(可切换)
- 持久化:Chroma 本地目录 + BM25 内存索引(启动重建)
"""
import os
import re
import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ===== 配置(从 config.py 导入) =====
from agent_core.config import (
    KB_PERSIST_DIR,
    KB_EMBEDDING_PROVIDER,
    KB_EMBEDDING_MODEL,
    KB_EMBEDDING_API_KEY,
    KB_EMBEDDING_API_BASE,
    KB_CHUNK_SIZE,
    KB_CHUNK_OVERLAP,
    KB_PARENT_CHUNK_SIZE,
    KB_MINERU_BACKEND,
    KB_MINERU_TIMEOUT,
)

# ===== 数据结构 =====
@dataclass
class Chunk:
    chunk_id: str
    text: str
    parent_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


# ===== Embedding 抽象层(双模式) =====
class _Embedder:
    """Embedding 抽象层:本地 sentence-transformers 或 OpenAI 兼容 API。"""
    def __init__(self):
        self._provider = KB_EMBEDDING_PROVIDER
        self._model = None
        self._client = None

    def _ensure_loaded(self):
        if self._provider == "local":
            if self._model is None:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading local embedding model: %s", KB_EMBEDDING_MODEL)
                self._model = SentenceTransformer(KB_EMBEDDING_MODEL)
        else:  # api 模式
            if self._client is None:
                import httpx
                self._client = httpx.AsyncClient(
                    base_url=KB_EMBEDDING_API_BASE,
                    headers={"Authorization": f"Bearer {KB_EMBEDDING_API_KEY}"},
                    timeout=30.0,
                )

    def encode_sync(self, texts: list[str]) -> list[list[float]]:
        """同步编码(本地模式用)。"""
        self._ensure_loaded()
        return self._model.encode(texts).tolist()

    async def encode_async(self, texts: list[str]) -> list[list[float]]:
        """异步编码(API 模式用)。"""
        self._ensure_loaded()
        if self._provider == "local":
            # 本地模型 CPU 密集,丢线程池避免阻塞事件循环
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._model.encode, texts)
        # API 模式
        resp = await self._client.post(
            "/embeddings",
            json={"model": KB_EMBEDDING_MODEL, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]


# ===== 知识库主类 =====
class KnowledgeBase:
    """单进程知识库:BM25 + Dense + RRF 融合,父子分块。"""

    def __init__(self, persist_dir: str = None):
        self.persist_dir = Path(persist_dir or KB_PERSIST_DIR)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_size = KB_CHUNK_SIZE
        self.chunk_overlap = KB_CHUNK_OVERLAP
        self.parent_chunk_size = KB_PARENT_CHUNK_SIZE

        self._embedder = _Embedder()
        self._chroma = None  # 懒加载,避免 import 时副作用
        self._collection = None
        self._chunks: dict[str, Chunk] = {}
        self._bm25 = None
        self._tokenized: list[list[str]] = []
        self._chunk_ids_order: list[str] = []
        self._loaded = False

    def _ensure_chroma(self):
        if self._chroma is None:
            import chromadb
            self._chroma = chromadb.PersistentClient(path=str(self.persist_dir / "chroma"))
            self._collection = self._chroma.get_or_create_collection("kb")

    def _ensure_loaded(self):
        """首次访问时从 Chroma 重建内存索引(BM25 + chunks 字典)。"""
        if self._loaded:
            return
        self._ensure_chroma()
        # 从 Chroma 拉所有 chunk 重建内存结构
        if self._collection.count() > 0:
            all_data = self._collection.get(include=["documents", "metadatas"])
            for cid, doc, meta in zip(all_data["ids"], all_data["documents"], all_data["metadatas"]):
                parent_id = meta.get("parent_id") if meta else None
                self._chunks[cid] = Chunk(cid, doc, parent_id, meta or {})
                # 父块也需进 _chunks 字典,但父块不入向量库(见 add_document 逻辑)
            # 补全父块(父块文本需要单独持久化或从子块聚合 — 简化方案:父块也入向量库,标记 type=parent)
        self._rebuild_bm25()
        self._loaded = True

    # ---------- 文档入库 ----------
    async def add_document(self, file_path: str) -> int:
        """用 MinerU 解析文档 → Markdown → 分块入库。返回新增 chunk 数。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._add_document_sync, file_path)

    def _add_document_sync(self, file_path: str) -> int:
        md_text = self._parse_with_mineru(file_path)
        if not md_text.strip():
            return 0
        new_chunks = self._split_markdown(md_text, source=file_path)

        # 所有 chunk(父+子)都入向量库,父块标记 type=parent
        # 这样检索时父子都能被命中,父块作为完整章节上下文
        if new_chunks:
            embeddings = self._embedder.encode_sync([c.text for c in new_chunks])
            self._ensure_chroma()
            self._collection.add(
                ids=[c.chunk_id for c in new_chunks],
                embeddings=embeddings,
                documents=[c.text for c in new_chunks],
                metadatas=[{"parent_id": c.parent_id, **c.metadata} for c in new_chunks],
            )

        for c in new_chunks:
            self._chunks[c.chunk_id] = c
        self._rebuild_bm25()
        return len(new_chunks)

    def _parse_with_mineru(self, file_path: str) -> str:
        """调 MinerU 子进程解析,返回 Markdown 文本。"""
        with tempfile.TemporaryDirectory() as tmp:
            try:
                subprocess.run(
                    ["mineru", "-p", file_path, "-o", tmp,
                     "--backend", KB_MINERU_BACKEND],
                    check=True,
                    capture_output=True,
                    timeout=KB_MINERU_TIMEOUT,
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"MinerU 解析失败: {e.stderr.decode(errors='replace')}")
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"MinerU 解析超时(>{KB_MINERU_TIMEOUT}s)")

            # MinerU 输出:{tmp}/{stem}/auto/{stem}.md
            stem = Path(file_path).stem
            md_file = Path(tmp) / stem / "auto" / f"{stem}.md"
            if not md_file.exists():
                md_files = list(Path(tmp).rglob("*.md"))
                if not md_files:
                    raise RuntimeError(f"MinerU 未输出 Markdown")
                md_file = md_files[0]
            return md_file.read_text(encoding="utf-8")

    def _split_markdown(self, md_text: str, source: str) -> list[Chunk]:
        """按 H2 章节分块,父子结构。父块=H2 章节,子块=章节内段落滑窗。"""
        new_chunks: list[Chunk] = []
        stem = Path(source).stem

        sections = re.split(r'(^## .+$)', md_text, flags=re.MULTILINE)

        def _make_chunks(parent_id: str, parent_text: str, section_title: str, content: str):
            new_chunks.append(Chunk(parent_id, parent_text, None,
                                     {"source": source, "type": "parent", "section": section_title}))
            if content.strip():
                sub = self._split_by_paragraph(content, self.chunk_size, self.chunk_overlap)
                for c_idx, c_text in enumerate(sub):
                    new_chunks.append(Chunk(
                        f"{parent_id}_c{c_idx}", c_text, parent_id,
                        {"source": source, "type": "child", "section": section_title},
                    ))

        # 处理 H2 之前的前言
        if sections and not sections[0].startswith('## ') and sections[0].strip():
            _make_chunks(f"{stem}_s_pre", sections[0].strip(), "_preface", sections[0])

        # 处理各 H2 章节
        s_idx = 1
        while s_idx < len(sections):
            if sections[s_idx].startswith('## '):
                title = sections[s_idx][3:].strip()
                content = sections[s_idx + 1] if s_idx + 1 < len(sections) else ''
                parent_id = f"{stem}_s{s_idx}"
                parent_text = f"## {title}\n{content}".strip()
                _make_chunks(parent_id, parent_text, title, content)
                s_idx += 2
            else:
                s_idx += 1
        return new_chunks

    def _split_by_paragraph(self, text: str, max_size: int, overlap: int) -> list[str]:
        """按段落切,段落超长再滑窗。表格行(|开头)整体保留不切。"""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks = []
        buf = ''
        for p in paragraphs:
            is_table = p.startswith('|')
            if is_table and len(p) > max_size:
                # 表格超长也整体保留(不切),标记截断
                if buf:
                    chunks.append(buf)
                    buf = ''
                chunks.append(p)
                continue
            if len(buf) + len(p) + 2 <= max_size:
                buf = f"{buf}\n\n{p}" if buf else p
            else:
                if buf:
                    chunks.append(buf)
                if len(p) <= max_size:
                    buf = p
                else:
                    for i in range(0, len(p), max_size - overlap):
                        chunks.append(p[i:i + max_size])
                    buf = ''
        if buf:
            chunks.append(buf)
        return chunks

    # ---------- 混合检索 ----------
    async def search(self, query: str, top_k: int = 5,
                     bm25_weight: float = 0.4, dense_weight: float = 0.6) -> list[dict]:
        """BM25 + Dense + RRF 融合检索。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._search_sync, query, top_k, bm25_weight, dense_weight)

    def _search_sync(self, query, top_k, bm25_w, dense_w) -> list[dict]:
        self._ensure_loaded()

        # BM25 召回
        bm25_hits = {}
        if self._bm25 is not None:
            tokens = list(jieba.cut(query)) if _use_jieba else query.split()
            scores = self._bm25.get_scores(tokens)
            ranked = sorted(enumerate(scores), key=lambda x: -x[1])[:top_k * 3]
            for rank, (idx, _) in enumerate(ranked):
                cid = self._chunk_ids_order[idx]
                bm25_hits[cid] = 1.0 / (60 + rank)  # RRF k=60

        # Dense 召回
        query_emb = self._embedder.encode_sync([query])[0]
        dense_results = self._collection.query(query_embeddings=[query_emb], n_results=top_k * 3)
        dense_hits = {}
        for rank, cid in enumerate(dense_results["ids"][0]):
            dense_hits[cid] = 1.0 / (60 + rank)

        # RRF 融合
        all_ids = set(bm25_hits) | set(dense_hits)
        fused = sorted(
            all_ids,
            key=lambda cid: bm25_w * bm25_hits.get(cid, 0) + dense_w * dense_hits.get(cid, 0),
            reverse=True,
        )[:top_k]

        # 父块扩展:命中子块时返回父块文本作为上下文
        results = []
        seen_parents = set()
        for cid in fused:
            chunk = self._chunks.get(cid)
            if not chunk:
                continue
            # 如果命中子块,且父块尚未输出,改输出父块(完整章节)
            if chunk.parent_id and chunk.parent_id in seen_parents:
                continue
            context_text = chunk.text
            context_id = cid
            if chunk.parent_id:
                parent = self._chunks.get(chunk.parent_id)
                if parent:
                    context_text = parent.text
                    context_id = parent.chunk_id
                    seen_parents.add(context_id)
            results.append({
                "chunk_id": context_id,
                "text": context_text,
                "score": bm25_w * bm25_hits.get(cid, 0) + dense_w * dense_hits.get(cid, 0),
                "source": chunk.metadata.get("source", ""),
                "section": chunk.metadata.get("section", ""),
            })
        return results

    # ---------- 索引维护 ----------
    def _rebuild_bm25(self):
        """从所有 chunk 重建 BM25 索引(只用子块,父块已通过扩展返回)。"""
        child_ids = [cid for cid, c in self._chunks.items() if c.parent_id is not None]
        if not child_ids:
            self._bm25 = None
            return
        self._chunk_ids_order = child_ids
        self._tokenized = [self._tokenize(self._chunks[cid].text) for cid in child_ids]
        from rank_bm25 import BM25Okapi
        self._bm25 = BM25Okapi(self._tokenized)

    def _tokenize(self, text: str) -> list[str]:
        """中文用 jieba,英文用 split。"""
        if _use_jieba:
            return list(jieba.cut(text))
        return text.split()

    def stats(self) -> dict:
        """返回知识库统计信息。"""
        self._ensure_loaded()
        return {
            "total_chunks": len(self._chunks),
            "parent_chunks": sum(1 for c in self._chunks.values() if c.parent_id is None),
            "child_chunks": sum(1 for c in self._chunks.values() if c.parent_id is not None),
            "persist_dir": str(self.persist_dir),
        }


# ===== 单例管理 =====
_kb_instances: dict[str, KnowledgeBase] = {}

def get_kb(namespace: str = "default") -> KnowledgeBase:
    """获取或创建知识库单例。namespace 隔离不同知识库。"""
    if namespace not in _kb_instances:
        persist = Path(KB_PERSIST_DIR) / namespace
        _kb_instances[namespace] = KnowledgeBase(persist_dir=str(persist))
    return _kb_instances[namespace]


# ===== jieba 懒加载 =====
_use_jieba = False
def _init_jieba():
    global _use_jieba, jieba
    try:
        import jieba
        _use_jieba = True
    except ImportError:
        _use_jieba = False
_init_jieba()


# ===== @tool 工具函数 =====
@tool
def kb_search(query: str, top_k: int = 5, namespace: str = "default") -> str:
    """检索本地知识库,返回相关文档片段。适用于:产品文档、内部资料、已入库的 PDF/Word/PPT/Markdown 解析内容。

    当用户问题涉及已入库的本地文档时,优先用本工具而非 web_search。
    检索采用 BM25 + 向量混合 + RRF 融合,命中子块自动扩展返回完整章节作为上下文。

    Args:
        query: 检索查询(自然语言或关键词均可)
        top_k: 返回的最大结果数,默认 5
        namespace: 知识库命名空间,默认 "default"
    """
    async def _run() -> str:
        kb = get_kb(namespace)
        results = await kb.search(query, top_k=top_k)
        if not results:
            return f"[知识库 {namespace} 无匹配结果]"
        parts = [f"[知识库 {namespace} 命中 {len(results)} 条]"]
        for r in results:
            src = f"来源: {r['source']} | 章节: {r['section']}" if r['section'] else f"来源: {r['source']}"
            parts.append(f"[{src}]\n{r['text']}")
        return "\n\n---\n\n".join(parts)

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.exception("kb_search failed")
        return f"知识库检索出错: {str(e)}"


@tool
def kb_add_document(file_path: str, namespace: str = "default") -> str:
    """向知识库添加文档(MinerU 解析),支持 PDF/Word/PPT/图片等格式。返回入库结果。

    解析后按 Markdown H2 章节做父子分块,父块为完整章节,子块为章节内段落。

    Args:
        file_path: 文档绝对路径(支持 PDF/DOCX/PPTX/图片等 MinerU 能识别的格式)
        namespace: 知识库命名空间,默认 "default"
    """
    async def _run() -> str:
        kb = get_kb(namespace)
        count = await kb.add_document(file_path)
        return f"已入库 {count} 个 chunks,文件: {file_path},命名空间: {namespace}"

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.exception("kb_add_document failed")
        return f"文档入库出错: {str(e)}"
```

**关键设计决策**:
- **懒加载**:Chroma、Embedder、jieba 都懒加载,避免 import 时副作用(符合现有 `ensure_runtime_dirs` 模式)
- **父子块都入向量库**:简化重建逻辑(从 Chroma get 一次就能恢复全部),父块标记 `type=parent`,检索时去重
- **父块扩展去重**:命中同一父块的多个子块时,只返回一次父块文本
- **表格保护**:`_split_by_paragraph` 识别 `|` 开头的表格行,超长也整体保留
- **错误处理**:与 web_search 一致,`try/except` 返回中文 str,不 raise

#### 2. `d:\project\tools\kb_manage.py`(管理脚本,约 80 行)

**职责**:批量入库、查看统计、重建索引的命令行工具,供用户手动管理知识库。

```python
# tools/kb_manage.py
"""知识库管理 CLI:批量入库、查看统计、清空命名空间。
用法:
  python -m tools.kb_manage ingest <dir_or_file> [--namespace default]
  python -m tools.kb_manage stats [--namespace default]
  python -m tools.kb_manage clear [--namespace default]
"""
import argparse
import asyncio
from pathlib import Path
from tools.kb_tool import get_kb

SUPPORTED_EXT = {".pdf", ".docx", ".pptx", ".txt", ".md", ".html", ".png", ".jpg", ".jpeg"}

async def cmd_ingest(target: str, namespace: str):
    kb = get_kb(namespace)
    p = Path(target)
    files = []
    if p.is_file():
        files = [p]
    elif p.is_dir():
        files = [f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED_EXT]
    else:
        print(f"路径不存在: {target}")
        return
    if not files:
        print(f"未找到支持的文件(支持: {SUPPORTED_EXT})")
        return
    print(f"待入库 {len(files)} 个文件到命名空间 [{namespace}]...")
    success, failed = 0, 0
    for f in files:
        try:
            count = await kb.add_document(str(f))
            print(f"  ✓ {f.name} → {count} chunks")
            success += 1
        except Exception as e:
            print(f"  ✗ {f.name} → {e}")
            failed += 1
    print(f"完成:成功 {success},失败 {failed}")

async def cmd_stats(namespace: str):
    kb = get_kb(namespace)
    s = kb.stats()
    print(f"命名空间: {namespace}")
    for k, v in s.items():
        print(f"  {k}: {v}")

async def cmd_clear(namespace: str):
    import shutil
    from tools.kb_tool import _kb_instances
    kb = get_kb(namespace)
    shutil.rmtree(kb.persist_dir, ignore_errors=True)
    _kb_instances.pop(namespace, None)
    print(f"已清空命名空间: {namespace}")

def main():
    ap = argparse.ArgumentParser(description="知识库管理工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_ingest = sub.add_parser("ingest", help="批量入库")
    p_ingest.add_argument("target", help="文件或目录路径")
    p_ingest.add_argument("--namespace", default="default")
    p_stats = sub.add_parser("stats", help="查看统计")
    p_stats.add_argument("--namespace", default="default")
    p_clear = sub.add_parser("clear", help="清空命名空间")
    p_clear.add_argument("--namespace", default="default")
    args = ap.parse_args()
    if args.cmd == "ingest":
        asyncio.run(cmd_ingest(args.target, args.namespace))
    elif args.cmd == "stats":
        asyncio.run(cmd_stats(args.namespace))
    elif args.cmd == "clear":
        asyncio.run(cmd_clear(args.namespace))

if __name__ == "__main__":
    main()
```

### 修改文件(4 个)

#### 3. `d:\project\tools\__init__.py`

**改动**:导出 kb_search 和 kb_add_document

**当前内容**(11 行):
```python
from tools.web_search import web_search
from tools.render_html import render_html
from tools.get_current_time import get_current_time
__all__ = ["web_search", "render_html", "get_current_time"]
```

**改后**:
```python
from tools.web_search import web_search
from tools.render_html import render_html
from tools.get_current_time import get_current_time
from tools.kb_tool import kb_search, kb_add_document
__all__ = ["web_search", "render_html", "get_current_time", "kb_search", "kb_add_document"]
```

#### 4. `d:\project\agent_core\config.py`

**改动**:在文件末尾(第 39 行 `SEARCH_PROVIDER_COOLDOWN_SECONDS` 之后)新增 KB 配置块

**新增内容**(追加在 L39 后,在 `def ensure_runtime_dirs` 之前):
```python
# ===== 知识库(kb_tool)配置 =====
# Embedding 提供方: "local"(本地 sentence-transformers,默认) 或 "api"(OpenAI 兼容 API)
KB_EMBEDDING_PROVIDER: str = os.getenv("KB_EMBEDDING_PROVIDER", "local")
# 本地模式:模型名(首次启动下载,约 100MB)
KB_EMBEDDING_MODEL: str = os.getenv("KB_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
# API 模式:OpenAI 兼容 embeddings 端点
KB_EMBEDDING_API_BASE: str = os.getenv("KB_EMBEDDING_API_BASE", "")
KB_EMBEDDING_API_KEY: str = os.getenv("KB_EMBEDDING_API_KEY", "")
# 知识库持久化根目录(按 namespace 分子目录)
KB_PERSIST_DIR: str = os.getenv("KB_PERSIST_DIR", str(WORKSPACE_ROOT / "kb_store"))
# 分块参数
KB_CHUNK_SIZE: int = int(os.getenv("KB_CHUNK_SIZE", "500"))
KB_CHUNK_OVERLAP: int = int(os.getenv("KB_CHUNK_OVERLAP", "50"))
KB_PARENT_CHUNK_SIZE: int = int(os.getenv("KB_PARENT_CHUNK_SIZE", "2000"))
# MinerU 解析配置
KB_MINERU_BACKEND: str = os.getenv("KB_MINERU_BACKEND", "vlm-sglang")
KB_MINERU_TIMEOUT: int = int(os.getenv("KB_MINERU_TIMEOUT", "300"))
```

**同时**在 `ensure_runtime_dirs()` 函数内(L48-50)追加:
```python
Path(KB_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
```

#### 5. `d:\project\agent_core\prompts.py`

**改动 1**:L6 import 增加 kb_search
```python
from tools import web_search, kb_search, kb_add_document
```

**改动 2**:L18 "通用编排原则" 增加一条知识库路由提示(在"检索委托给子 agent"之后):
```
- **本地知识库优先**:用户问题涉及已入库文档(产品文档/内部资料/PDF 等)时,委托 research-agent 并提示其用 kb_search;时效性/外部信息才用 web_search。
```

**改动 3**:research_subagent 定义(L24-39)更新 system_prompt + tools:
```python
research_subagent = {
    "name": "research-agent",
    "description": (
        "委托研究子任务。每次只给一个明确的主题/问题。"
        "子 agent 会搜索(本地知识库或网络)并把发现写到 /tmp/research/<topic>.md。"
        "返回摘要 + 文件路径。"
    ),
    "system_prompt": (
        "你是通用研究助手。接到任务后:\n"
        "1. 判断信息来源:本地知识库(产品文档/内部资料/已入库 PDF)用 kb_search;外部/时效性信息用 web_search\n"
        "2. 可多角度换关键词搜几次,把发现用 write_file 写入 /tmp/research/<主题>.md(含来源)\n"
        "3. 返回简短摘要 + 文件路径\n"
        "原则:本地知识优先 kb_search,外部信息用 web_search,不要在上下文堆大量结果。\n"
        "如需向知识库添加新文档,用 kb_add_document 工具。"
    ),
    "tools": [web_search, kb_search, kb_add_document],
}
```

#### 6. `d:\project\.env.example`

**改动**:末尾追加 KB 配置样板
```env
# ===== 知识库(kb_tool)=====
# Embedding 提供方: local(本地,默认) / api(OpenAI 兼容)
KB_EMBEDDING_PROVIDER=local
# 本地模式模型名(首次启动下载约 100MB)
KB_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
# API 模式配置(仅 KB_EMBEDDING_PROVIDER=api 时需要)
KB_EMBEDDING_API_BASE=
KB_EMBEDDING_API_KEY=
# 知识库持久化目录(默认 workspace/kb_store)
KB_PERSIST_DIR=
# 分块参数
KB_CHUNK_SIZE=500
KB_CHUNK_OVERLAP=50
KB_PARENT_CHUNK_SIZE=2000
# MinerU 解析配置
KB_MINERU_BACKEND=vlm-sglang
KB_MINERU_TIMEOUT=300
```

### 不需要改动的文件(明确说明)

- `d:\project\entrypoints\web.py` — SSE 层不变,新工具自动产生 tool_call/tool_result 事件
- `d:\project\agent_core\runtime.py` — kb_search 不挂主 agent(用户决策),`build_agent()` 的 tools 列表不变
- `d:\project\agent_core\llm.py` — LLM 配置不变
- 前端所有文件 — 复用现有 toolCalls 通用渲染(MessageBubble.vue L324-363),无需 SSE 事件类型扩展

## 依赖安装

```bash
# 核心依赖
pip install chromadb rank_bm25 sentence-transformers jieba

# MinerU(按官方文档装,依赖较重,首次运行下 VLM 权重约几 GB)
pip install mineru
```

> MinerU 装好后首次调用会下载 VLM 权重,建议提前手动跑一次 `mineru -p test.pdf -o ./test_out --backend vlm-sglang` 预热。

## 假设与决策

1. **MinerU 调用方式**:命令行子进程(`subprocess.run`),不走 HTTP server 模式。理由:简单、无额外服务;首次调用慢(起进程+加载模型),但知识库入库是低频操作,可接受。若后续高频入库可升级为 server 模式。
2. **父子块都入向量库**:简化重建逻辑,代价是存储翻倍(可接受)。父块标记 `type=parent`,检索时去重。
3. **BM25 中文分词**:优先用 jieba,未装则降级为 `split()`。通过 `_use_jieba` 全局标志懒加载判断,不影响 import。
4. **namespace 隔离**:不同知识库用子目录隔离(如 `workspace/kb_store/default/`、`workspace/kb_store/product_docs/`),单例字典缓存实例。
5. **前端零改动**:kb_search 调用结果(检索到的 chunks 拼接文本)走通用 toolCalls 卡片,在思考区折叠展示。output 会被 web.py L627 截断到 500 字符预览,完整内容已通过 LLM 上下文传递,不影响答案质量。
6. **不在主 agent 注册 kb_search**:用户决策,保持主 agent 工具精简,通过 research_subagent 间接调用,与现有架构一致。
7. **不实现 GraphRAG / 重排序**:MVP 阶段够用,后续可渐进加 bge-reranker。

## 验证步骤

### 1. 单元验证(无需启动服务)

```bash
# 在项目根目录
python -c "
from tools.kb_tool import KnowledgeBase, get_kb
kb = get_kb('test')
print('KB 初始化成功:', kb.stats())
"
```

预期输出:`KB 初始化成功: {'total_chunks': 0, 'parent_chunks': 0, 'child_chunks': 0, ...}`

### 2. MinerU 解析验证

```bash
# 准备一个测试 PDF(放 workspace/uploads/test.pdf)
python -c "
import asyncio
from tools.kb_tool import get_kb
async def t():
    kb = get_kb('test')
    n = await kb.add_document('workspace/uploads/test.pdf')
    print(f'入库 {n} chunks')
    print(kb.stats())
asyncio.run(t())
"
```

预期:看到 "入库 N chunks",stats 显示 total_chunks > 0。

### 3. 检索验证

```bash
python -c "
import asyncio
from tools.kb_tool import get_kb
async def t():
    kb = get_kb('test')
    r = await kb.search('测试查询', top_k=3)
    for hit in r:
        print(f'[{hit[\"source\"]} | {hit[\"section\"]}] score={hit[\"score\"]:.4f}')
        print(hit['text'][:200])
        print('---')
asyncio.run(t())
"
```

### 4. 工具注册验证

```bash
python -c "
from agent_core.runtime import build_agent
agent = build_agent()
# 检查 research_subagent 是否包含 kb_search
from agent_core.prompts import research_subagent
print('subagent tools:', [t.name for t in research_subagent['tools']])
"
```

预期输出包含:`['web_search', 'kb_search', 'kb_add_document']`

### 5. 端到端 SSE 验证

1. 启动后端:`python run.py`
2. 前端发起对话:"帮我检索本地知识库里关于 XXX 的内容"
3. 观察:
   - 主 agent 调用 task 委托 research-agent
   - 前端收到 `subagent_start` 事件
   - research-agent 调用 `kb_search`,前端收到 `tool_call`(name=kb_search)+ `tool_result`
   - MessageBubble 思考区显示 kb_search 工具卡片
   - 最终答案基于检索结果生成

### 6. 管理脚本验证

```bash
python -m tools.kb_manage stats --namespace default
python -m tools.kb_manage ingest workspace/uploads/ --namespace default
python -m tools.kb_manage stats --namespace default
```

## 实施顺序(推荐)

1. 改 `agent_core/config.py`(加配置常量)
2. 改 `.env.example`(加 env 样板)
3. 新建 `tools/kb_tool.py`(核心实现)
4. 新建 `tools/kb_manage.py`(管理脚本)
5. 改 `tools/__init__.py`(导出)
6. 改 `agent_core/prompts.py`(挂载到 research_subagent)
7. 装依赖:`pip install chromadb rank_bm25 sentence-transformers jieba`
8. 跑验证步骤 1-4
9. (可选)装 MinerU,跑验证步骤 5-6
