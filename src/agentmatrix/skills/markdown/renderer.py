"""
Markdown 渲染器

将 AST 树渲染为 Markdown 文本。

核心思想：由于在 MarkdownNode.content 中保留了"原汁原味"的 Markdown 源码切片，
只需对 AST 进行一次 DFS 遍历，拼接所有节点的内容。
"""

from typing import List
from .ast import MarkdownNode


class MarkdownRenderer:
    """
    Markdown 渲染器

    职责：
    - DFS 遍历 AST
    - 根据节点类型添加正确的换行符
    - 渲染为 Markdown 文本
    """

    def render(self, root_node: MarkdownNode) -> str:
        """
        渲染 AST 为 Markdown 文本

        Args:
            root_node: 根节点

        Returns:
            Markdown 文本
        """
        return self._render_node(root_node, is_root=True)

    def _render_node(self, node: MarkdownNode, is_root: bool = False) -> str:
        """
        递归渲染节点

        Args:
            node: 当前节点
            is_root: 是否为根节点

        Returns:
            渲染后的文本
        """
        # 根节点特殊处理
        if node.node_type == "root":
            parts = []
            for i, child in enumerate(node.children):
                # 子节点之间用 \n\n 分隔
                if i > 0:
                    parts.append("\n\n")
                parts.append(self._render_node(child))
            return ''.join(parts)

        # 标题节点：添加 # 符号
        if node.node_type in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            level = int(node.node_type[1])
            prefix = "#" * level
            title = node.title or node.content
            result = f"{prefix} {title}"

            # 渲染子节点
            if node.children:
                result += "\n\n"
                for i, child in enumerate(node.children):
                    if i > 0:
                        result += "\n\n"
                    result += self._render_node(child)

            return result

        # 段落节点
        if node.node_type == "paragraph":
            result = node.content

            # 渲染子节点
            if node.children:
                result += "\n\n"
                for i, child in enumerate(node.children):
                    if i > 0:
                        result += "\n\n"
                    result += self._render_node(child)

            return result

        # 代码块节点：用 ``` 包裹
        if node.node_type == "code_block":
            # 检测语言（第一行是否包含语言标识）
            lines = node.content.split('\n')
            if lines and lines[0].strip().startswith('```'):
                # 已经有 ``` 标记，直接返回
                return node.content
            else:
                # 添加 ``` 标记
                return f"```\n{node.content}\n```"

        # 列表节点
        if node.node_type == "list":
            return node.content

        # 默认情况
        result = node.content

        # 渲染子节点
        if node.children:
            for i, child in enumerate(node.children):
                if i > 0:
                    result += "\n\n"
                result += self._render_node(child)

        return result
