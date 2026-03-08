"""
Markdown AST 数据结构

定义 Markdown 文档的抽象语法树，包括：
- MarkdownNode: 节点类（标题、段落、代码块等）
- VirtualChunk: 虚拟分块（用于超大节点）
- MarkdownAST: AST 管理类（CRUD 操作、TOC 生成等）
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import re


@dataclass
class VirtualChunk:
    """
    虚拟分块：用于超大节点的内容分块

    当节点超过 8K tokens 时，自动触发虚拟分块。
    虚拟分块通过字符偏移量映射到父节点的内容，实现零拷贝。

    Attributes:
        chunk_id: 分块 ID（如 "root/h1_1/code_1/chunk_01"）
        start_char: 起始字符位置（相对于 parent.content）
        end_char: 结束字符位置（相对于 parent.content）
    """
    chunk_id: str
    start_char: int
    end_char: int

    @property
    def content(self) -> str:
        """获取分块内容（需要从 parent 获取）"""
        raise NotImplementedError("VirtualChunk 需要通过 MarkdownNode 获取内容")


@dataclass
class MarkdownNode:
    """
    Markdown 节点：AST 的基本单元

    Attributes:
        node_id: 绝对路径 ID（如 "root/h1_1/h2_2/p_3"）
        node_type: 节点类型（"root", "h1"-"h6", "paragraph", "code_block", "list"）
        title: 可读标题（如 "1.1 背景介绍"），用于 TOC 生成
        content: 节点自身的纯文本（标题节点不包含 # 符号）
        children: 子节点列表
        char_count: 字符数
        token_count: 估算 Token 数（约 char_count / 4）
        is_dirty: 脏标记（被修改过为 True）
        is_large_node: 是否超过 8K tokens 阈值
        virtual_chunks: 虚拟分块列表（仅当 is_large_node=True 时使用）
        parent: 父节点引用（用于向上遍历）
    """
    node_id: str
    node_type: str
    title: Optional[str] = None
    content: str = ""
    children: List['MarkdownNode'] = field(default_factory=list)
    char_count: int = 0
    token_count: int = 0
    is_dirty: bool = False
    is_large_node: bool = False
    virtual_chunks: Optional[List[VirtualChunk]] = None
    parent: Optional['MarkdownNode'] = None

    def __post_init__(self):
        """初始化后计算元数据"""
        self._update_metadata()

    def _update_metadata(self):
        """更新元数据（字符数、token数）"""
        self.char_count = len(self.content)
        # 粗略估算：1 token ≈ 4 字符（英文），中文约 2 字符 = 1 token
        # 这里使用保守估计：1 token ≈ 3 字符
        self.token_count = max(1, self.char_count // 3)

        # 检测是否需要虚拟分块（8K tokens）
        if self.token_count > 8000:
            self.is_large_node = True
            self._create_virtual_chunks()
        else:
            self.is_large_node = False
            self.virtual_chunks = None

    def _create_virtual_chunks(self):
        """
        创建虚拟分块（降级瀑布流策略）

        切分策略：
        1. 尝试按 \n\n 切（保证段落完整）
        2. 若单段仍超标，按 \n 切（保证代码行/表格行完整）
        3. 若仍超标，按标点符号 。、. 切
        4. 最后手段：按固定字符数强制切分
        """
        if self.token_count <= 8000:
            return

        content = self.content
        chunks = []
        chunk_index = 1

        # 策略1: 按 \n\n 切
        paragraphs = content.split('\n\n')
        current_chunk = ""
        current_start = 0

        for para in paragraphs:
            test_chunk = current_chunk + ('\n\n' if current_chunk else '') + para
            test_tokens = len(test_chunk) // 3

            if test_tokens <= 8000:
                current_chunk = test_chunk
            else:
                # 当前段落会导致超出，先保存当前分块
                if current_chunk:
                    chunks.append(VirtualChunk(
                        chunk_id=f"{self.node_id}/chunk_{chunk_index:02d}",
                        start_char=current_start,
                        end_char=current_start + len(current_chunk)
                    ))
                    chunk_index += 1
                    current_start += len(current_chunk)

                # 检查单个段落是否超标
                para_tokens = len(para) // 3
                if para_tokens <= 8000:
                    current_chunk = para
                else:
                    # 策略2: 单个段落超标，按 \n 切
                    self._split_large_paragraph(para, chunks, chunk_index, current_start)
                    chunk_index = len(chunks) + 1
                    current_chunk = ""
                    current_start += len(para)

        # 保存最后一个分块
        if current_chunk:
            chunks.append(VirtualChunk(
                chunk_id=f"{self.node_id}/chunk_{chunk_index:02d}",
                start_char=current_start,
                end_char=len(content)
            ))

        self.virtual_chunks = chunks

    def _split_large_paragraph(self, paragraph: str, chunks: List[VirtualChunk], start_index: int, offset: int):
        """切分超大段落（按 \n 切）"""
        lines = paragraph.split('\n')
        current_chunk = ""
        current_start = offset

        for line in lines:
            test_chunk = current_chunk + ('\n' if current_chunk else '') + line
            test_tokens = len(test_chunk) // 3

            if test_tokens <= 8000:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(VirtualChunk(
                        chunk_id=f"{self.node_id}/chunk_{start_index:02d}",
                        start_char=current_start,
                        end_char=current_start + len(current_chunk)
                    ))
                    start_index += 1
                    current_start += len(current_chunk)

                current_chunk = line

        if current_chunk:
            chunks.append(VirtualChunk(
                chunk_id=f"{self.node_id}/chunk_{start_index:02d}",
                start_char=current_start,
                end_char=current_start + len(current_chunk)
            ))

    def get_chunk_content(self, chunk_index: int) -> str:
        """
        获取虚拟分块的内容

        Args:
            chunk_index: 分块索引（从 1 开始）

        Returns:
            分块内容
        """
        if not self.virtual_chunks:
            raise ValueError(f"节点 {self.node_id} 没有虚拟分块")

        if chunk_index < 1 or chunk_index > len(self.virtual_chunks):
            raise ValueError(f"分块索引超出范围: {chunk_index}（共 {len(self.virtual_chunks)} 个分块）")

        chunk = self.virtual_chunks[chunk_index - 1]
        return self.content[chunk.start_char:chunk.end_char]

    def add_child(self, child: 'MarkdownNode'):
        """添加子节点"""
        child.parent = self
        self.children.append(child)

    def find_child_by_index(self, index: int) -> Optional['MarkdownNode']:
        """按索引查找子节点"""
        if 0 <= index < len(self.children):
            return self.children[index]
        return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于调试）"""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "title": self.title,
            "content_preview": self.content[:100] + "..." if len(self.content) > 100 else self.content,
            "char_count": self.char_count,
            "token_count": self.token_count,
            "is_dirty": self.is_dirty,
            "is_large_node": self.is_large_node,
            "virtual_chunks_count": len(self.virtual_chunks) if self.virtual_chunks else 0,
            "children_count": len(self.children)
        }


class MarkdownAST:
    """
    Markdown AST 管理类

    职责：
    - 维护根节点
    - 提供 CRUD 操作（get_node, get_parent）
    - 生成 TOC
    - 搜索关键字
    - 管理脏标记
    """

    def __init__(self, root_node: MarkdownNode):
        """
        初始化 AST

        Args:
            root_node: 根节点
        """
        self.root_node = root_node
        self._node_map: Dict[str, MarkdownNode] = {}
        self._build_node_map(root_node)

    def _build_node_map(self, node: MarkdownNode):
        """构建节点 ID 到节点的映射（加速查询）"""
        self._node_map[node.node_id] = node
        for child in node.children:
            self._build_node_map(child)

    def get_node(self, node_id: str) -> Optional[MarkdownNode]:
        """
        根据 node_id 获取节点

        Args:
            node_id: 节点 ID（如 "root/h1_1/h2_2/p_3"）

        Returns:
            MarkdownNode 或 None
        """
        return self._node_map.get(node_id)

    def get_parent(self, node: MarkdownNode) -> Optional[MarkdownNode]:
        """
        获取节点的父节点

        Args:
            node: 子节点

        Returns:
            父节点或 None（根节点没有父节点）
        """
        return node.parent

    def get_toc(self, depth: int = 2) -> str:
        """
        生成文档目录（TOC）

        Args:
            depth: 最大深度（默认 2）

        Returns:
            TOC 字符串
        """
        lines = []
        self._collect_toc(self.root_node, current_depth=0, max_depth=depth, lines=lines)
        return '\n'.join(lines)

    def _collect_toc(self, node: MarkdownNode, current_depth: int, max_depth: int, lines: List[str]):
        """递归收集 TOC"""
        if current_depth > max_depth:
            return

        # 只显示标题节点（h1-h6）
        if node.node_type in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            indent = "  " * (current_depth - 1)
            level = int(node.node_type[1])
            title = node.title or node.content
            lines.append(f"{indent}{level}. {title} [{node.node_id}]")

            # 递归处理子节点
            for child in node.children:
                self._collect_toc(child, current_depth + 1, max_depth, lines)
        elif node.node_type == "root":
            # 根节点：递归处理子节点
            for child in node.children:
                self._collect_toc(child, current_depth + 1, max_depth, lines)

    def search_keywords(self, query: str, context_lines: int = 2) -> str:
        """
        搜索关键字

        Args:
            query: 搜索关键词或正则表达式
            context_lines: 上下文行数（默认 2）

        Returns:
            搜索结果字符串
        """
        results = []

        try:
            # 尝试按正则表达式编译
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            # 如果编译失败，按字面字符串搜索
            pattern = None

        for node_id, node in self._node_map.items():
            if node.node_type == "root":
                continue

            # 搜索节点内容
            if pattern:
                matches = list(pattern.finditer(node.content))
            else:
                # 字面字符串搜索
                matches = []
                start = 0
                while True:
                    idx = node.content.lower().find(query.lower(), start)
                    if idx == -1:
                        break
                    # 创建简单的匹配对象
                    class Match:
                        def __init__(self, start, end):
                            self.start = start
                            self.end = end
                    matches.append(Match(idx, idx + len(query)))
                    start = idx + 1

            if matches:
                # 提取上下文
                lines = node.content.split('\n')
                for match in matches:
                    # 获取匹配位置（处理 regex match 对象和自定义 Match 对象）
                    if callable(getattr(match, 'start', None)):
                        # regex match 对象
                        match_start = match.start()
                    else:
                        # 自定义 Match 对象
                        match_start = match.start

                    # 找到匹配所在的行号
                    char_count = 0
                    match_line = 0
                    for i, line in enumerate(lines):
                        char_count += len(line) + 1  # +1 for \n
                        if char_count >= match_start:
                            match_line = i
                            break

                    # 提取上下文行
                    start_line = max(0, match_line - context_lines)
                    end_line = min(len(lines), match_line + context_lines + 1)
                    context = '\n'.join(lines[start_line:end_line])

                    results.append(f"📍 {node.node_id} (行 {match_line + 1})\n{context}\n")

        if not results:
            return f"未找到关键词: {query}"

        return f"找到 {len(results)} 处匹配:\n\n" + '\n'.join(results)

    def has_dirty_nodes(self) -> bool:
        """检查是否有脏节点"""
        return any(node.is_dirty for node in self._node_map.values())

    def clear_dirty_flags(self):
        """清除所有脏标记"""
        for node in self._node_map.values():
            node.is_dirty = False

    def get_dirty_nodes(self) -> List[MarkdownNode]:
        """获取所有脏节点"""
        return [node for node in self._node_map.values() if node.is_dirty]

    def rebuild_node_map(self):
        """重建节点映射（在添加/删除节点后调用）"""
        self._node_map.clear()
        self._build_node_map(self.root_node)
