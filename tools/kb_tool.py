"""自包含知识库工具,设计参考 WeKnora,纯 Python 实现。
- 文档解析:MinerU(子进程)→ Markdown
- 分块:Markdown H2 章节感知 + 段落滑窗,父子结构
- 检索:BM25(rank_bm25) + Dense(Chroma) + RRF 融合
- Embedding:本地 BGE-small-zh(默认) / OpenAI 兼容 API(可切换)
- 持久化:Chroma 本地目录 + BM25 内存索引(启动重建)

注意:本模块直接读 os.getenv 而非 from agent_core.config import ...,
以避免循环 import(agent_core 包初始化会拉 runtime → build_agent → 需要 tools)。
配置项与 agent_core/config.py 的 KB_* 常量保持同步。
"""
import os
import re
import sys
import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# 注意:不在此处 load_dotenv(),由 agent_core/config.py 启动时统一加载。

# ===== 配置(直接读 env,与 agent_core/config.py 保持同步) =====
_WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", "workspace"))
KB_PERSIST_DIR: str = os.getenv("KB_PERSIST_DIR", str(_WORKSPACE_ROOT / "kb_store"))
KB_EMBEDDING_PROVIDER: str = os.getenv("KB_EMBEDDING_PROVIDER", "local")
KB_EMBEDDING_MODEL: str = os.getenv("KB_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
KB_EMBEDDING_API_BASE: str = os.getenv("KB_EMBEDDING_API_BASE", "")
KB_EMBEDDING_API_KEY: str = os.getenv("KB_EMBEDDING_API_KEY", "")
KB_CHUNK_SIZE: int = int(os.getenv("KB_CHUNK_SIZE", "500"))
KB_CHUNK_OVERLAP: int = int(os.getenv("KB_CHUNK_OVERLAP", "50"))
KB_PARENT_CHUNK_SIZE: int = int(os.getenv("KB_PARENT_CHUNK_SIZE", "2000"))
KB_MINERU_BACKEND: str = os.getenv("KB_MINERU_BACKEND", "pipeline")
KB_MINERU_TIMEOUT: int = int(os.getenv("KB_MINERU_TIMEOUT", "300"))

# ===== jieba 懒加载 =====
# 模块级标志 + 名字占位,实际 import 在 _init_jieba() 中尝试。
# 未安装时 _use_jieba=False,所有用到 jieba.cut 的地方都通过 _use_jieba 短路保护。
_use_jieba = False
jieba = None


def _init_jieba() -> None:
    """尝试加载 jieba(中文分词)。失败则降级为 split()。"""
    global _use_jieba, jieba
    try:
        import jieba as _jieba  # type: ignore
        jieba = _jieba
        _use_jieba = True
    except ImportError:
        _use_jieba = False


_init_jieba()


# ===== 数据结构 =====
@dataclass
class Chunk:
    chunk_id: str
    text: str
    parent_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


# ===== Embedding 抽象层(双模式) =====
class _Embedder:
    """Embedding 抽象层:本地 sentence-transformers 或 OpenAI 兼容 API。

    API 模式复用同一个同步 httpx.Client(连接池复用),避免每次 encode 新建 Client。
    """

    def __init__(self):
        self._provider = KB_EMBEDDING_PROVIDER
        self._model = None
        self._client = None  # API 模式:同步 httpx.Client(持久化复用)

    def _ensure_loaded(self):
        if self._provider == "local":
            if self._model is None:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading local embedding model: %s", KB_EMBEDDING_MODEL)
                self._model = SentenceTransformer(KB_EMBEDDING_MODEL)
        else:  # api 模式:复用同步 Client
            if self._client is None:
                import httpx
                self._client = httpx.Client(
                    base_url=KB_EMBEDDING_API_BASE,
                    headers={"Authorization": f"Bearer {KB_EMBEDDING_API_KEY}"},
                    timeout=30.0,
                )

    def encode_sync(self, texts: list[str]) -> list[list[float]]:
        """同步编码。本地模式调模型;API 模式调 OpenAI 兼容端点(复用 Client)。"""
        self._ensure_loaded()
        if self._provider == "local":
            return self._model.encode(texts).tolist()
        # API 模式:同步调用(被 run_in_executor 包裹,不阻塞事件循环)
        resp = self._client.post(
            "/embeddings",
            json={"model": KB_EMBEDDING_MODEL, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]


# ===== 知识库主类 =====
class KnowledgeBase:
    """单进程知识库:BM25 + Dense + RRF 融合,父子分块。"""

    def __init__(self, persist_dir: str = None, namespace: str = "default"):
        self.namespace = namespace
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
            self._collection = self._chroma.get_or_create_collection(f"kb_{self.namespace}")

    def _ensure_loaded(self):
        """首次访问时从 Chroma 重建内存索引(BM25 + chunks 字典)。"""
        if self._loaded:
            return
        self._ensure_chroma()
        # 从 Chroma 拉所有 chunk 重建内存结构
        if self._collection.count() > 0:
            all_data = self._collection.get(include=["documents", "metadatas"])
            for cid, doc, meta in zip(
                all_data["ids"], all_data["documents"], all_data["metadatas"]
            ):
                # Chroma metadata 不支持 None,父块存空字符串,此处转回 None
                parent_id = (meta.get("parent_id") or None) if meta else None
                self._chunks[cid] = Chunk(cid, doc, parent_id, meta or {})
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
        # 用 upsert 避免同文件重复入库时 DuplicateIDError
        # Chroma metadata 不支持 None,parent_id 存空字符串表示父块
        if new_chunks:
            embeddings = self._embedder.encode_sync([c.text for c in new_chunks])
            self._ensure_chroma()
            self._collection.upsert(
                ids=[c.chunk_id for c in new_chunks],
                embeddings=embeddings,
                documents=[c.text for c in new_chunks],
                metadatas=[{"parent_id": c.parent_id or "", **c.metadata} for c in new_chunks],
            )

        for c in new_chunks:
            self._chunks[c.chunk_id] = c
        self._rebuild_bm25()
        return len(new_chunks)

    def _parse_with_mineru(self, file_path: str) -> str:
        """复用 mineru skill 的 extract.py 脚本(云 API,免本地 torch/GPU)。

        extract.py 内部自动降级:extract(token)→ flash-extract(免 token)→ 报错。
        输出 Markdown 到临时目录,读取后返回。
        """
        # 定位 skill 脚本(skill 实际在 workspace/skills/ 下)
        candidates = [
            Path("workspace/skills/mineru/scripts/extract.py"),  # 从 workspace 根运行
            Path("skills/mineru/scripts/extract.py"),            # 兼容旧路径
            Path(__file__).resolve().parent.parent / "workspace" / "skills" / "mineru" / "scripts" / "extract.py",
        ]
        script = next((p for p in candidates if p.exists()), None)
        if not script:
            raise RuntimeError(
                "找不到 workspace/skills/mineru/scripts/extract.py,请确认 mineru skill 已安装"
            )

        # 定位 python(用当前解释器,确保 .env 能被 skill 读取)
        python = sys.executable

        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "out.md"
            cmd = [
                python, str(script),
                file_path,
                "-o", str(out_file),
                "--format", "md",
                "--timeout", str(KB_MINERU_TIMEOUT),
            ]
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=KB_MINERU_TIMEOUT + 30,  # 留余量给脚本自身
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(Path.cwd()),  # 确保 skill 能找到 .env
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"MinerU 解析超时(>{KB_MINERU_TIMEOUT}s)")

            if result.returncode != 0:
                raise RuntimeError(
                    f"MinerU 解析失败: {result.stderr.strip() or result.stdout.strip()}"
                )

            # extract.py 输出可能是文件也可能是目录
            if out_file.is_file():
                return out_file.read_text(encoding="utf-8")
            # 目录形式:extract.py 用 -o output/out.md 时,out.md 是文件
            # 但用 -o output/out/ 时会输出 out/xxx.md
            if out_file.is_dir():
                md_files = list(out_file.rglob("*.md"))
                if md_files:
                    return md_files[0].read_text(encoding="utf-8")
            # 兜底:在 tmp 里找 md
            md_files = list(Path(tmp).rglob("*.md"))
            if md_files:
                return md_files[0].read_text(encoding="utf-8")
            raise RuntimeError(
                f"MinerU 解析成功但未输出 Markdown。stdout: {result.stdout[:200]}"
            )

    def _split_markdown(self, md_text: str, source: str) -> list[Chunk]:
        """按 H1/H2 章节分块,父子结构。父块=章节,子块=章节内段落滑窗。"""
        new_chunks: list[Chunk] = []
        stem = Path(source).stem

        # 同时按 H1 和 H2 切分,保留分隔符
        sections = re.split(r'(^#{1,2} .+$)', md_text, flags=re.MULTILINE)

        def _make_chunks(parent_id: str, parent_text: str, section_title: str, content: str):
            # 父块超过安全上限时,只保留标题占位(避免单块过大导致 LLM API 报错)
            MAX_PARENT = 3000
            parent_text_safe = parent_text if len(parent_text) <= MAX_PARENT else f"[{section_title}]"
            new_chunks.append(
                Chunk(
                    parent_id,
                    parent_text_safe,
                    None,
                    {"source": source, "type": "parent", "section": section_title},
                )
            )
            if content.strip():
                sub = self._split_by_paragraph(content, self.chunk_size, self.chunk_overlap)
                for c_idx, c_text in enumerate(sub):
                    new_chunks.append(
                        Chunk(
                            f"{parent_id}_c{c_idx}",
                            c_text,
                            parent_id,
                            {"source": source, "type": "child", "section": section_title},
                        )
                    )

        # 处理首个标题之前的前言
        if sections and not sections[0].startswith('#'):
            if sections[0].strip():
                _make_chunks(f"{stem}_s_pre", sections[0].strip(), "_preface", sections[0])

        # 处理各章节(H1 或 H2)
        s_idx = 1
        while s_idx < len(sections):
            if sections[s_idx].startswith('#'):
                title = sections[s_idx].lstrip('#').strip()
                content = sections[s_idx + 1] if s_idx + 1 < len(sections) else ''
                parent_id = f"{stem}_s{s_idx}"
                parent_text = f"{sections[s_idx]}\n{content}".strip()
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
                # 表格超长也整体保留(不切),避免破坏表格结构
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
    async def search(
        self,
        query: str,
        top_k: int = 5,
        bm25_weight: float = 0.4,
        dense_weight: float = 0.6,
    ) -> list[dict]:
        """BM25 + Dense + RRF 融合检索。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._search_sync, query, top_k, bm25_weight, dense_weight
        )

    def _search_sync(self, query, top_k, bm25_w, dense_w) -> list[dict]:
        self._ensure_loaded()

        # BM25 召回
        bm25_hits = {}
        if self._bm25 is not None:
            tokens = list(jieba.cut(query)) if _use_jieba else query.split()
            scores = self._bm25.get_scores(tokens)
            ranked = sorted(enumerate(scores), key=lambda x: -x[1])[: top_k * 3]
            for rank, (idx, _) in enumerate(ranked):
                cid = self._chunk_ids_order[idx]
                bm25_hits[cid] = 1.0 / (60 + rank)  # RRF k=60

        # Dense 召回
        query_emb = self._embedder.encode_sync([query])[0]
        dense_results = self._collection.query(
            query_embeddings=[query_emb], n_results=top_k * 3
        )
        dense_hits = {}
        for rank, cid in enumerate(dense_results["ids"][0]):
            dense_hits[cid] = 1.0 / (60 + rank)

        # RRF 融合
        all_ids = set(bm25_hits) | set(dense_hits)
        fused = sorted(
            all_ids,
            key=lambda cid: bm25_w * bm25_hits.get(cid, 0)
            + dense_w * dense_hits.get(cid, 0),
            reverse=True,
        )[:top_k]

        # 父块扩展:命中子块时返回父块文本作为上下文,同一父块只输出一次。
        # 安全限制:父块文本超过 MAX_CONTEXT_CHARS 时回退用子块本身(避免单条
        # ToolMessage 过大导致 LLM API 报错,如 agnes 的 "unknown variant 'file'" )
        MAX_CONTEXT_CHARS = 2000
        results = []
        seen_parents = set()
        for cid in fused:
            chunk = self._chunks.get(cid)
            if not chunk:
                continue
            if chunk.parent_id and chunk.parent_id in seen_parents:
                continue
            context_text = chunk.text
            context_id = cid
            if chunk.parent_id:
                parent = self._chunks.get(chunk.parent_id)
                if parent and len(parent.text) <= MAX_CONTEXT_CHARS:
                    context_text = parent.text
                    context_id = parent.chunk_id
                    seen_parents.add(context_id)
                # 父块过大 → 用子块本身,不标记 seen_parents(允许同父块的其他子块也返回)
            results.append(
                {
                    "chunk_id": context_id,
                    "text": context_text,
                    "score": bm25_w * bm25_hits.get(cid, 0)
                    + dense_w * dense_hits.get(cid, 0),
                    "source": chunk.metadata.get("source", ""),
                    "section": chunk.metadata.get("section", ""),
                }
            )
        return results

    # ---------- 索引维护 ----------
    def _rebuild_bm25(self):
        """从所有 chunk 重建 BM25 索引(只用子块,父块通过扩展返回)。

        注意:每次 add_document 后都全量重 tokenize 所有 chunk,批量入库时会
        有 O(N^2) 开销。MVP 阶段可接受(入库是低频操作);后续可改为增量更新。
        """
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
        _kb_instances[namespace] = KnowledgeBase(persist_dir=str(persist), namespace=namespace)
    return _kb_instances[namespace]


# ===== @tool 工具函数 =====
@tool
def kb_search(query: str, top_k: int = 5, namespace: str = "default") -> str:
    """检索本地知识库,返回相关文档片段。适用于:产品文档、内部资料、已入库的 PDF/Word/PPT/Markdown 解析内容。

    当用户问题涉及已入库的本地文档时,优先用本工具而非 web_search。
    检索采用 BM25 + 向量混合 + RRF 融合,命中子块自动扩展返回完整章节作为上下文。

    返回格式:文本部分(供 LLM 引用)+ 末尾 JSON 元数据行(供前端解析引用来源)。
    前端识别 `<!--KB_REFS:...-->` 注释行,提取引用元数据,渲染专属面板。

    Args:
        query: 检索查询(自然语言或关键词均可)
        top_k: 返回的最大结果数,默认 5
        namespace: 知识库命名空间,默认 "default"
    """
    async def _run() -> str:
        import json

        kb = get_kb(namespace)
        results = await kb.search(query, top_k=top_k)
        if not results:
            return f"[知识库 {namespace} 无匹配结果]"

        # 安全限制:单条片段文本超过 1500 字符则截断(带省略号),
        # 防止整篇论文被塞进 ToolMessage 导致 LLM API 报错
        MAX_PER_HIT = 1500
        # 总返回文本上限(不含元数据),超过则减少条数
        MAX_TOTAL_CHARS = 6000

        # 文本部分:供 LLM 阅读和引用
        parts = [f"[知识库 {namespace} 命中 {len(results)} 条]"]
        total_chars = 0
        for idx, r in enumerate(results):
            snippet = r["text"]
            if len(snippet) > MAX_PER_HIT:
                snippet = snippet[:MAX_PER_HIT] + "…[截断]"
            if total_chars + len(snippet) > MAX_TOTAL_CHARS:
                parts.append(f"[后续 {len(results) - idx} 条因长度限制省略]")
                break
            src = (
                f"来源: {r['source']} | 章节: {r['section']}"
                if r['section']
                else f"来源: {r['source']}"
            )
            parts.append(f"[{idx + 1}/{len(results)} {src}]\n{snippet}")
            total_chars += len(snippet)
        text_part = "\n\n---\n\n".join(parts)

        # JSON 元数据:供前端解析,渲染引用来源面板。
        # 元数据里的 text 也截断到 MAX_PER_HIT,避免 SSE event 过大
        refs_meta = []
        for r in results:
            snippet = r["text"]
            if len(snippet) > MAX_PER_HIT:
                snippet = snippet[:MAX_PER_HIT] + "…[截断]"
            refs_meta.append(
                {
                    "source": r["source"],
                    "section": r["section"],
                    "text": snippet,
                    "score": round(r["score"], 4),
                    "chunk_id": r["chunk_id"],
                }
            )
        # 用 HTML 注释包裹 JSON,LLM 会忽略,前端用正则提取
        meta_part = f"<!--KB_REFS:{json.dumps(refs_meta, ensure_ascii=False)}-->"

        return f"{text_part}\n\n{meta_part}"

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
