"""
Markdown 解析器

使用 markdown-it-py 将 Markdown 文本解析为 AST。

四阶段 Pipeline：
1. 词法扫描 (Lexer & Tokenization)
2. 逻辑折叠与树构建 (Logical Tree Builder - Stack-based Folding)
3. 元数据与防御性切分 (Enrichment & Chunking Engine)
4. 寻址与 ID 挂载 (Addressing & ID Generation)
"""

from typing import List, Optional
from markdown_it import MarkdownIt
from markdown_it.token import Token
from .ast import MarkdownNode, MarkdownAST


class TokenContentExtractor:
    """
    Token 内容提取器

    由于 markdown-it-py 的 token.map 只提供行号范围，
    需要自己实现内容提取。
    """

    def __init__(self, raw_text: str):
        """
        初始化

        Args:
            raw_text: 原始 Markdown 文本
        """
        self.raw_text = raw_text
        self.lines = raw_text.split('\n')

    def extract_content(self, token: Token) -> str:
        """
        提取 Token 对应的原始内容

        Args:
            token: markdown-it-py 的 Token 对象

        Returns:
            原始内容字符串
        """
        if token.map is None:
            return ""

        start_line, end_line = token.map

        # 提取对应行（line number 从 0 开始）
        lines = self.lines[start_line:end_line + 1]
        return '\n'.join(lines)


class MarkdownParser:
    """
    Markdown 解析器

    使用 Stack-based Folding 算法将扁平的 Token 流转换为 AST 树。
    """

    def __init__(self):
        """初始化解析器"""
        self.md = MarkdownIt().enable('strikethrough').enable('table')

    def parse(self, file_path: str) -> MarkdownAST:
        """
        解析 Markdown 文件

        Args:
            file_path: Markdown 文件路径

        Returns:
            MarkdownAST 对象
        """
        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        return self.parse_text(raw_text)

    def parse_text(self, text: str) -> MarkdownAST:
        """
        解析 Markdown 文本

        Args:
            text: Markdown 文本

        Returns:
            MarkdownAST 对象
        """
        # 阶段1: 词法扫描
        tokens = self.md.parse(text)

        # 初始化内容提取器
        extractor = TokenContentExtractor(text)

        # 阶段2: 逻辑折叠与树构建（Stack-based Folding）
        root_node = self._build_ast(tokens, extractor)

        # 阶段4: 寻址与 ID 挂载
        self._assign_node_ids(root_node)

        # 阶段3: 元数据与防御性切分（在 MarkdownNode.__post_init__ 中自动完成）
        # 递归触发元数据更新
        self._update_metadata(root_node)

        return MarkdownAST(root_node)

    def _build_ast(self, tokens: List[Token], extractor: TokenContentExtractor) -> MarkdownNode:
        """
        构建 AST（Stack-based Folding）

        核心算法：
        1. 维护一个栈，初始时推入 RootNode
        2. 遍历 Token 流，根据原始行号切片获取该 Token 的原汁原味内容
        3. 遇到非标题块（Paragraph, Code, Table）：直接作为当前栈顶节点的子节点
        4. 遇到标题块（H1 ~ H6）：
           - 比较当前标题级别与栈顶节点的级别
           - 如果当前级别 > 栈顶级别：将当前标题作为栈顶的子节点，压入栈顶
           - 如果当前级别 == 栈顶级别：弹出栈顶，将当前标题作为新栈顶的子节点，压入栈顶
           - 如果当前级别 < 栈顶级别：一直弹栈，直到栈顶级别 > 当前级别

        边界情况处理：
        - 标题跳跃（H1 → H3）：直接入栈
        - 标题回退（H1 → H2 → H3 → H2）：弹出 H3，将新 H2 作为 H1 的子节点
        - 非标题块：直接作为当前栈顶节点的子节点

        Args:
            tokens: Token 流
            extractor: 内容提取器

        Returns:
            根节点
        """
        # 创建根节点
        root = MarkdownNode(
            node_id="root",
            node_type="root",
            title="Root",
            content=""
        )

        # 栈结构：[(node, level)]
        # level 用于标题节点（1-6），非标题节点 level=0
        stack = [(root, 0)]

        i = 0
        while i < len(tokens):
            token = tokens[i]
            token_type = token.type

            # 处理标题块
            if token_type == "heading_open":
                level = int(token.tag[1])  # h1 -> 1, h2 -> 2

                # 提取标题内容（下一个 token 应该是 inline）
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    content = extractor.extract_content(tokens[i + 1])
                    # 去掉 # 符号（如果有）
                    content = content.lstrip('#').strip()

                    # 创建标题节点
                    heading_node = MarkdownNode(
                        node_id="",  # 稍后分配
                        node_type=token.tag,  # h1, h2, etc.
                        title=content,
                        content=content
                    )

                    # Stack-based Folding
                    self._push_to_stack(stack, heading_node, level)

                    # 跳过 heading_close
                    i += 3
                    continue

            # 处理段落
            elif token_type == "paragraph_open":
                # 提取段落内容
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    content = extractor.extract_content(tokens[i + 1])

                    paragraph_node = MarkdownNode(
                        node_id="",  # 稍后分配
                        node_type="paragraph",
                        content=content
                    )

                    # 作为当前栈顶节点的子节点
                    stack[-1][0].add_child(paragraph_node)

                    i += 3
                    continue

            # 处理代码块
            elif token_type == "fence" or token_type == "code_block":
                content = extractor.extract_content(token)

                code_node = MarkdownNode(
                    node_id="",  # 稍后分配
                    node_type="code_block",
                    content=content
                )

                # 作为当前栈顶节点的子节点
                stack[-1][0].add_child(code_node)

                i += 1
                continue

            # 处理列表
            elif token_type == "bullet_list_open" or token_type == "ordered_list_open":
                # 提取列表内容
                list_content = []
                j = i + 1
                list_depth = 1

                while j < len(tokens) and list_depth > 0:
                    t = tokens[j]
                    if t.type in ["bullet_list_close", "ordered_list_close"]:
                        list_depth -= 1
                    elif t.type in ["bullet_list_open", "ordered_list_open"]:
                        list_depth += 1
                    elif t.type == "inline":
                        list_content.append(extractor.extract_content(t))
                    j += 1

                list_node = MarkdownNode(
                    node_id="",  # 稍后分配
                    node_type="list",
                    content='\n'.join(list_content)
                )

                # 作为当前栈顶节点的子节点
                stack[-1][0].add_child(list_node)

                i = j
                continue

            # 其他 token，跳过
            i += 1

        return root

    def _push_to_stack(self, stack: List, node: MarkdownNode, level: int):
        """
        将节点推入栈（Stack-based Folding 核心逻辑）

        Args:
            stack: 栈 [(node, level)]
            node: 要插入的节点
            level: 标题级别（1-6）
        """
        # 比较当前级别与栈顶级别
        while len(stack) > 1:
            top_node, top_level = stack[-1]

            if top_level < level:
                # 当前级别 > 栈顶级别：作为栈顶的子节点，压入栈
                top_node.add_child(node)
                stack.append((node, level))
                return
            elif top_level == level:
                # 当前级别 == 栈顶级别：弹出栈顶，作为新栈顶的子节点，压入栈
                stack.pop()
                new_top = stack[-1][0]
                new_top.add_child(node)
                stack.append((node, level))
                return
            else:
                # 当前级别 < 栈顶级别：弹出栈顶，继续比较
                stack.pop()

        # 如果栈为空或只剩 root，作为 root 的子节点
        stack[0][0].add_child(node)
        stack.append((node, level))

    def _assign_node_ids(self, root: MarkdownNode):
        """
        为节点分配 ID（深度优先遍历）

        ID 格式：root/h1_1/h2_2/p_3

        Args:
            root: 根节点
        """
        # 计数器：记录每种节点类型的出现次数
        counters = {}

        def dfs(node: MarkdownNode, parent_id: str):
            """递归分配 ID"""
            # 计数
            node_type = node.node_type
            if node_type not in counters:
                counters[node_type] = 0
            counters[node_type] += 1

            # 生成 ID
            if parent_id:
                node.node_id = f"{parent_id}/{node_type}_{counters[node_type]}"
            else:
                node.node_id = f"{node_type}_{counters[node_type]}"

            # 递归处理子节点
            for child in node.children:
                dfs(child, node.node_id)

        dfs(root, "")

    def _update_metadata(self, node: MarkdownNode):
        """
        递归更新元数据（触发虚拟分块）

        Args:
            node: 节点
        """
        node._update_metadata()
        for child in node.children:
            self._update_metadata(child)
