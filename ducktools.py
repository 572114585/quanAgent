from langchain_core.tools import tool
from ddgs import DDGS

@tool
def web_search(query: str,max_results: int=5) -> str:
    """用duckduckgo工具来进行搜搜query，返回前max_results个结果中的标题、链接和摘要"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))#, safesearch="on"
            
        if not results:
            return "没有找到相关结果"
            
        parts = []
        for item in results:
            title = item.get("title", "（无标题）")
            href = item.get("href", "（无链接）")
            body = item.get("body", "（无摘要）")
            parts.append(f"[{title}]({href})\n{body}")

        return "\n\n---\n\n".join(parts)
    except Exception as e:
        return f"搜索时出错：{str(e)}"
