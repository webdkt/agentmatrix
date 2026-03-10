"""
Markdown Skill - 提供 Markdown 文档编辑能力

核心特性：
- 单层架构：只有 MarkdownSkillMixin，直接提供所有 actions
- AST 虚拟文件树：将 Markdown 解析为带元数据的树状结构
- Docker 容器支持：自动路径转换（容器内路径 → 宿主机路径）
- 职责边界清晰：只处理"编辑现有内容"，不处理"创作新内容"

所有 actions 都需要 file_path 参数，支持多文件操作。
"""

import json
import logging
from typing import Optional, Tuple
from pathlib import Path

from ...core.action import register_action
from .parser import MarkdownParser
from .renderer import MarkdownRenderer
from .ast import MarkdownAST, MarkdownNode


logger = logging.getLogger(__name__)


class MarkdownSkillMixin:
    """
    Markdown Skill Mixin

    提供 Markdown 文档的解析、编辑、搜索、总结等功能。

    关键设计：
    - 所有 actions 都需要 file_path 参数（支持多文件操作）
    - AST 缓存支持多文件：_ast_cache = {file_path: ast}
    - Docker 路径自动转换：容器内路径 → 宿主机路径
    - MicroAgent 生命周期内复用 AST 缓存
    """

    # 🆕 Skill 级别元数据
    _skill_description = "Markdown 文档编辑技能：编辑、总结、搜索 Markdown 文档内容"

    _skill_usage_guide = """
使用场景：
- 需要编辑 Markdown 文档
- 需要总结文档内容
- 需要搜索或查看文档结构

使用建议：
- 使用 get_toc 查看文档目录结构
- 使用 search_keywords 搜索关键词
- 使用 modify_node 修改节点内容
- 使用 save_markdown 保存修改

注意事项：
- 所有 actions 都需要 file_path 参数
- 修改后记得调用 save_markdown 保存
"""

    # ==================== 私有方法 ====================

    def __init__(self, *args, **kwargs):
        """初始化"""
        super().__init__(*args, **kwargs)
        # AST 缓存：支持多文件
        self._ast_cache: dict[str, MarkdownAST] = {}

    def _get_docker_manager(self):
        """获取 docker_manager"""
        if hasattr(self, 'root_agent') and self.root_agent:
            if hasattr(self.root_agent, 'docker_manager'):
                return self.root_agent.docker_manager

        # 兼容：自己就是 root_agent
        if hasattr(self, 'docker_manager'):
            return self.docker_manager

        return None

    def _get_current_session_id(self) -> str:
        """
        获取当前 user_session_id

        用于 Docker 路径转换。
        """
        if hasattr(self, 'current_user_session_id'):
            return self.current_user_session_id
        elif hasattr(self, 'root_agent') and hasattr(self.root_agent, 'current_user_session_id'):
            return self.root_agent.current_user_session_id
        else:
            return "default"

    def _resolve_to_host_path(self, container_path: str) -> str:
        """
        容器内路径 → 宿主机路径

        路径映射规则：
        - /work_files/test.md → {workspace_root}/agent_files/{agent_name}/work_files/{session_id}/test.md
        - /SKILLS/git-workflow/skill.md → {workspace_root}/SKILLS/git-workflow/skill.md
        - /home/plan.md → {workspace_root}/agent_files/{agent_name}/home/plan.md

        Args:
            container_path: 容器内路径或宿主机路径

        Returns:
            宿主机路径
        """
        docker_manager = self._get_docker_manager()

        # 非 Docker 环境：直接返回原路径
        if not docker_manager:
            return container_path

        # 检查是否已经是宿主机路径（如果文件存在，则认为是宿主机路径）
        from pathlib import Path
        if Path(container_path).exists():
            return container_path

        # Docker 环境：转换路径
        if container_path.startswith("/work_files/"):
            relative_path = container_path[len("/work_files/"):]
            session_id = self._get_current_session_id()
            return str(docker_manager.work_files_base / session_id / relative_path)
        elif container_path.startswith("/SKILLS/"):
            relative_path = container_path[len("/SKILLS/"):]
            return str(docker_manager.skills_dir / relative_path)
        elif container_path.startswith("/home/"):
            relative_path = container_path[len("/home/"):]
            return str(docker_manager.agent_home / relative_path)
        else:
            # 可能是宿主机路径，直接返回
            return container_path

    def _get_ast(self, file_path: str) -> MarkdownAST:
        """
        获取或创建 AST（支持多文件缓存）

        Args:
            file_path: 文件路径（可以是容器内路径或宿主机路径）

        Returns:
            MarkdownAST 对象
        """
        # 转换为宿主机路径（用于缓存 key）
        host_path = self._resolve_to_host_path(file_path)

        # 检查缓存
        if host_path in self._ast_cache:
            logger.debug(f"♻️  使用缓存的 AST: {host_path}")
            return self._ast_cache[host_path]

        # 解析 Markdown
        logger.info(f"📄 解析 Markdown: {host_path}")
        parser = MarkdownParser()
        ast = parser.parse(host_path)
        self._ast_cache[host_path] = ast

        return ast

    def _get_root_agent(self):
        """获取 root_agent"""
        if hasattr(self, 'root_agent') and self.root_agent:
            return self.root_agent
        return self

    async def _call_llm_directly(self, prompt: str) -> str:
        """
        直接调用 LLM（用于意图验证、内容修改、总结）

        Args:
            prompt: 提示词

        Returns:
            LLM 响应
        """
        root_agent = self._get_root_agent()

        # 调用 root_agent 的 LLM
        if hasattr(root_agent, 'call_llm'):
            response = await root_agent.call_llm(messages=[{"role": "user", "content": prompt}])
            return response
        else:
            raise RuntimeError("root_agent 没有 call_llm 方法")

    async def _rewrite_with_llm(self, content: str, instruction: str) -> str:
        """
        使用 LLM 修改内容

        Args:
            content: 原始内容
            instruction: 修改指令

        Returns:
            修改后的内容
        """
        prompt = f"""你是一个专业的文档编辑。请根据以下指令修改内容：

【修改指令】
{instruction}

【原始内容】
{content}

【要求】
1. 只返回修改后的内容，不要解释
2. 保持 Markdown 格式
3. 只修改现有内容，不要添加新内容
4. 保持原文的结构和风格

请直接输出修改后的内容："""

        return await self._call_llm_directly(prompt)

    async def _summarize_with_llm(self, content: str) -> str:
        """
        使用 LLM 总结内容

        Args:
            content: 原始内容

        Returns:
            总结
        """
        prompt = f"""请总结以下内容：

【内容】
{content}

【要求】
1. 提取关键信息
2. 简洁明了
3. 不超过 200 字

总结："""

        return await self._call_llm_directly(prompt)

    # ==================== Actions ====================

    @register_action(
        "获取 Markdown 文档的目录结构（TOC）",
        param_infos={
            "file_path": "Markdown 文件路径",
            "depth": "目录深度（默认 2）"
        }
    )
    async def get_toc(self, file_path: str, depth: int = 2) -> str:
        """
        获取文档目录

        Args:
            file_path: 文件路径
            depth: 目录深度（默认 2）

        Returns:
            TOC 字符串
        """
        ast = self._get_ast(file_path)
        return ast.get_toc(depth)

    @register_action(
        "在 Markdown 文档中搜索关键字",
        param_infos={
            "file_path": "Markdown 文件路径",
            "query": "搜索关键词或正则表达式",
            "context_lines": "上下文行数（默认 2）"
        }
    )
    async def search_keywords(self, file_path: str, query: str, context_lines: int = 2) -> str:
        """
        搜索关键字

        Args:
            file_path: 文件路径
            query: 搜索关键词
            context_lines: 上下文行数（默认 2）

        Returns:
            搜索结果
        """
        ast = self._get_ast(file_path)
        return ast.search_keywords(query, context_lines)

    @register_action(
        "读取 Markdown 节点的内容",
        param_infos={
            "file_path": "Markdown 文件路径",
            "node_id": "节点 ID（如 root/h1_1/h2_2/p_3）"
        }
    )
    async def read_node_content(self, file_path: str, node_id: str) -> str:
        """
        读取节点内容

        Args:
            file_path: 文件路径
            node_id: 节点 ID

        Returns:
            节点内容
        """
        ast = self._get_ast(file_path)
        node = ast.get_node(node_id)

        if node is None:
            return f"错误：未找到节点 {node_id}"

        # 检查是否为超大节点
        if node.is_large_node and node.virtual_chunks:
            return f"""节点 {node_id} 过大（{node.token_count} tokens），已被虚拟分块为 {len(node.virtual_chunks)} 个分块。

请使用以下方式读取：
- 指定分块索引：read_node_chunk(file_path="{file_path}", node_id="{node_id}", chunk_index=1)
- 或使用 summarize_node 总结内容

节点预览（前 500 字符）：
{node.content[:500]}...
"""

        return node.content

    @register_action(
        "修改 Markdown 节点的内容",
        param_infos={
            "file_path": "Markdown 文件路径",
            "node_id": "节点 ID",
            "edit_instruction": "修改指令（如'把A改为B'）"
        }
    )
    async def modify_node(self, file_path: str, node_id: str, edit_instruction: str) -> str:
        """
        修改节点内容（改写表述方式）

        Args:
            file_path: 文件路径
            node_id: 节点 ID
            edit_instruction: 修改指令

        Returns:
            执行结果
        """
        ast = self._get_ast(file_path)
        node = ast.get_node(node_id)

        if node is None:
            return f"错误：未找到节点 {node_id}"

        # 调用 LLM 修改
        modified_content = await self._rewrite_with_llm(node.content, edit_instruction)

        # 更新 AST
        node.content = modified_content
        node.is_dirty = True

        return f"✅ 已修改节点 {node_id}"

    @register_action(
        "精确替换文本",
        param_infos={
            "file_path": "Markdown 文件路径",
            "node_id": "节点 ID",
            "old_str": "原文",
            "new_str": "新内容"
        }
    )
    async def exact_replace(self, file_path: str, node_id: str, old_str: str, new_str: str) -> str:
        """
        精确替换文本

        Args:
            file_path: 文件路径
            node_id: 节点 ID
            old_str: 原文
            new_str: 新内容

        Returns:
            执行结果
        """
        ast = self._get_ast(file_path)
        node = ast.get_node(node_id)

        if node is None:
            return f"错误：未找到节点 {node_id}"

        if old_str not in node.content:
            return f"错误：'{old_str}' 不在节点 {node_id} 中"

        node.content = node.content.replace(old_str, new_str)
        node.is_dirty = True

        return f"✅ 已替换节点 {node_id} 中的文本"

    @register_action(
        "追加新节点",
        param_infos={
            "file_path": "Markdown 文件路径",
            "parent_id": "父节点 ID",
            "content": "新节点的内容（用户提供）",
            "node_type": "节点类型（如 h1, h2, paragraph, code_block）"
        }
    )
    async def append_new_node(
        self,
        file_path: str,
        parent_id: str,
        content: str,
        node_type: str = "paragraph"
    ) -> str:
        """
        在父节点后追加新节点

        Args:
            file_path: 文件路径
            parent_id: 父节点 ID
            content: 新节点的内容（用户提供）
            node_type: 节点类型（默认 paragraph）

        Returns:
            执行结果
        """
        ast = self._get_ast(file_path)
        parent_node = ast.get_node(parent_id)

        if parent_node is None:
            return f"错误：未找到父节点 {parent_id}"

        # 生成新节点 ID
        child_count = len(parent_node.children)
        new_node_id = f"{parent_id}/{node_type}_{child_count + 1}"

        # 创建新节点
        new_node = MarkdownNode(
            node_id=new_node_id,
            node_type=node_type,
            content=content
        )

        parent_node.add_child(new_node)
        new_node.is_dirty = True

        # 重建节点映射
        ast.rebuild_node_map()

        return f"✅ 已追加节点 {new_node_id}"

    @register_action(
        "插入新节点",
        param_infos={
            "file_path": "Markdown 文件路径",
            "after_node": "在哪个节点后插入（node_id）",
            "content": "新节点的内容（用户提供）",
            "node_type": "节点类型（默认 paragraph）"
        }
    )
    async def insert_node(
        self,
        file_path: str,
        after_node: str,
        content: str,
        node_type: str = "paragraph"
    ) -> str:
        """
        在指定节点后插入新节点

        Args:
            file_path: 文件路径
            after_node: 在哪个节点后插入（node_id）
            content: 新节点的内容（用户提供）
            node_type: 节点类型（默认 paragraph）

        Returns:
            执行结果
        """
        ast = self._get_ast(file_path)
        after_node_obj = ast.get_node(after_node)

        if after_node_obj is None:
            return f"错误：未找到节点 {after_node}"

        parent = ast.get_parent(after_node_obj)
        if parent is None:
            return f"错误：节点 {after_node} 没有父节点"

        # 生成新节点 ID
        index = parent.children.index(after_node_obj)
        new_node_id = f"{parent.node_id}/{node_type}_{index + 2}"

        # 创建新节点
        new_node = MarkdownNode(
            node_id=new_node_id,
            node_type=node_type,
            content=content
        )

        # 插入到指定位置
        parent.children.insert(index + 1, new_node)
        new_node.parent = parent
        new_node.is_dirty = True

        # 重建节点映射
        ast.rebuild_node_map()

        return f"✅ 已插入节点 {new_node_id}"

    @register_action(
        "删除节点",
        param_infos={
            "file_path": "Markdown 文件路径",
            "node_id": "要删除的节点 ID"
        }
    )
    async def delete_node(self, file_path: str, node_id: str) -> str:
        """
        删除节点

        Args:
            file_path: 文件路径
            node_id: 要删除的节点 ID

        Returns:
            执行结果
        """
        ast = self._get_ast(file_path)
        node = ast.get_node(node_id)

        if node is None:
            return f"错误：未找到节点 {node_id}"

        parent = ast.get_parent(node)
        if parent is None:
            return f"错误：不能删除根节点"

        # 删除节点
        parent.children.remove(node)

        # 重建节点映射
        ast.rebuild_node_map()

        return f"✅ 已删除节点 {node_id}"

    @register_action(
        "总结节点内容",
        param_infos={
            "file_path": "Markdown 文件路径",
            "node_id": "节点 ID"
        }
    )
    async def summarize_node(self, file_path: str, node_id: str) -> str:
        """
        总结节点内容

        Args:
            file_path: 文件路径
            node_id: 节点 ID

        Returns:
            总结
        """
        ast = self._get_ast(file_path)
        node = ast.get_node(node_id)

        if node is None:
            return f"错误：未找到节点 {node_id}"

        # 调用 LLM 总结
        summary = await self._summarize_with_llm(node.content)

        return f"📝 节点 {node_id} 的总结：\n\n{summary}"

    @register_action(
        "保存 Markdown 文件的修改",
        param_infos={
            "file_path": "Markdown 文件路径"
        }
    )
    async def save_markdown(self, file_path: str) -> str:
        """
        保存修改

        Args:
            file_path: 文件路径

        Returns:
            执行结果
        """
        ast = self._get_ast(file_path)

        # 渲染 AST 为 Markdown
        renderer = MarkdownRenderer()
        content = renderer.render(ast.root_node)

        # 转换为宿主机路径
        host_path = self._resolve_to_host_path(file_path)

        # 写入文件
        with open(host_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 清除 dirty 标记
        ast.clear_dirty_flags()

        return f"✅ 已保存 {file_path}"
