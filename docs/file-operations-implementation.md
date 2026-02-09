# File Operations 实现方案

## 一、技术选型

### 使用 LangChain FileManagementToolkit

**优势**:
- 成熟的实现,经过广泛使用
- 完善的安全机制(root_dir限制)
- 丰富的工具集(读、写、搜索、列表等)
- 正则表达式搜索支持

**安装**:
```bash
pip install langchain-community
```

**依赖添加** (pyproject.toml):
```toml
dependencies = [
    # ... 现有依赖
    "langchain-community>=0.3.0",
]
```

## 二、架构设计

### 2.1 主 Agent 侧 (Deep Researcher V2)

```python
# 在 deep_researcher_v2.py 中

@register_action
async def file_operation(operation_description: str) -> str:
    """
    执行文件操作

    这个action会启动一个File Micro Agent来处理具体的文件操作

    Args:
        operation_description: 自然语言描述的文件操作,例如:
            - "读取 overall_dashboard.md 的内容"
            - "在 Notebook 目录下创建新章节"
            - "搜索所有包含'机器学习'的文件"

    Returns:
        str: 操作结果
    """
    # 启动 File Micro Agent
    result = await file_micro_agent.execute(
        task=f"""
        用户要求执行文件操作:{operation_description}

        请解析用户意图,执行相应的操作。

        你可以使用以下具体 actions:
        - read_file: 读取文件内容
        - write_file: 写入文件内容
        - list_directory: 列出目录内容
        - search_files: 搜索文件(支持正则表达式)
        - copy_file: 复制文件
        - move_file: 移动文件
        - delete_file: 删除文件

        请执行操作并返回结果。
        """,
        available_actions=[
            "read_file",
            "write_file",
            "list_directory",
            "search_files",
            "copy_file",
            "move_file",
            "delete_file",
            "all_finished"
        ],
        max_steps=10
    )

    return result
```

### 2.2 File Micro Agent 实现

```python
# src/agentmatrix/skills/file_micro_agent.py

from ..agents.micro_agent import MicroAgent
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_community.tools.file_management import (
    ReadFileTool,
    WriteFileTool,
    ListDirectoryTool,
    FileSearchTool,
    CopyFileTool,
    MoveFileTool,
    DeleteFileTool
)
import asyncio
from pathlib import Path
from typing import Optional

class FileMicroAgent:
    """
    File Micro Agent - 专门处理文件操作的微代理

    特点:
    1. 使用 LangChain FileManagementToolkit 提供的工具
    2. 通过 root_dir 限制访问范围
    3. 提供 action 注册表供主 Agent 调用
    """

    def __init__(self, root_dir: str, brain, cerebellum):
        """
        初始化 File Micro Agent

        Args:
            root_dir: 文件操作的根目录(安全限制)
            brain: LLM 接口
            cerebellum: 参数协商器
        """
        self.root_dir = Path(root_dir).resolve()
        self.brain = brain
        self.cerebellum = cerebellum

        # 初始化 LangChain FileManagementToolkit
        self.toolkit = FileManagementToolkit(
            root_dir=str(self.root_dir)
        )

        # 创建 action registry
        self.action_registry = self._create_action_registry()

        # 创建 Micro Agent
        self.micro_agent = MicroAgent(
            brain=brain,
            cerebellum=cerebellum,
            action_registry=self.action_registry,
            name="FileMicroAgent",
            default_max_steps=10
        )

    def _create_action_registry(self) -> dict:
        """
        创建 action 注册表

        将 LangChain tools 包装成 async 函数
        """
        registry = {}

        # 获取所有 LangChain tools
        langchain_tools = {
            "read_file": ReadFileTool(root_dir=str(self.root_dir)),
            "write_file": WriteFileTool(root_dir=str(self.root_dir)),
            "list_directory": ListDirectoryTool(root_dir=str(self.root_dir)),
            "search_files": FileSearchTool(root_dir=str(self.root_dir)),
            "copy_file": CopyFileTool(root_dir=str(self.root_dir)),
            "move_file": MoveFileTool(root_dir=str(self.root_dir)),
            "delete_file": DeleteFileTool(root_dir=str(self.root_dir)),
        }

        # 包装成 async 函数并添加元数据
        for name, tool in langchain_tools.items():
            async def async_wrapper(**kwargs):
                # LangChain tools 是同步的,需要用 asyncio.to_thread 包装
                result = await asyncio.to_thread(tool.invoke, kwargs)
                return result

            # 添加 action 元数据
            async_wrapper._action_desc = tool.description
            async_wrapper._action_param_infos = tool.args_schema.schema()[
                "properties"
            ] if tool.args_schema else {}

            registry[name] = async_wrapper

        # 添加 all_finished action
        registry["all_finished"] = self._all_finished

        return registry

    async def _all_finished(self, result: str) -> str:
        """完成任务"""
        return result

    async def execute(
        self,
        task: str,
        available_actions: list[str],
        max_steps: int = 10,
        **kwargs
    ) -> str:
        """
        执行文件操作任务

        Args:
            task: 任务描述
            available_actions: 可用的 actions
            max_steps: 最大步数

        Returns:
            str: 执行结果
        """
        persona = """你是文件管理专家。

职责:
1. 理解用户的文件操作需求
2. 选择合适的工具执行操作
3. 返回清晰的执行结果

规则:
- 所有操作都限制在 {root_dir} 目录下
- 操作前先检查文件/目录是否存在
- 返回结果要简洁明了
- 遇到错误时给出清晰的错误信息
""".format(root_dir=str(self.root_dir))

        result = await self.micro_agent.execute(
            persona=persona,
            task=task,
            available_actions=available_actions,
            max_steps=max_steps,
            **kwargs
        )

        return result

    async def list_directory(self, directory_path: str = ".") -> str:
        """
        列出目录内容

        Args:
            directory_path: 目录路径(相对于 root_dir)

        Returns:
            str: 目录内容列表
        """
        list_tool = self.action_registry["list_directory"]
        result = await list_tool(dir_path=directory_path)
        return result

    async def read_file(self, file_path: str) -> str:
        """
        读取文件内容

        Args:
            file_path: 文件路径(相对于 root_dir)

        Returns:
            str: 文件内容
        """
        read_tool = self.action_registry["read_file"]
        result = await read_tool(file_path=file_path)
        return result

    async def write_file(self, file_path: str, content: str) -> str:
        """
        写入文件

        Args:
            file_path: 文件路径(相对于 root_dir)
            content: 文件内容

        Returns:
            str: 操作结果
        """
        write_tool = self.action_registry["write_file"]
        result = await write_tool(file_path=file_path, text=content)
        return result

    async def search_files(
        self,
        pattern: str,
        directory_path: str = "."
    ) -> str:
        """
        搜索文件

        Args:
            pattern: 搜索模式(正则表达式)
            directory_path: 搜索目录(相对于 root_dir)

        Returns:
            str: 搜索结果
        """
        search_tool = self.action_registry["search_files"]
        result = await search_tool(pattern=pattern, dir_path=directory_path)
        return result
```

### 2.3 集成到 Deep Researcher V2

```python
# src/agentmatrix/skills/deep_researcher_v2.py

class DeepResearcherV2:
    def __init__(self, workspace_root: str, brain, cerebellum):
        self.workspace_root = workspace_root

        # 初始化 File Micro Agent
        self.file_agent = FileMicroAgent(
            root_dir=workspace_root,
            brain=brain,
            cerebellum=cerebellum
        )

        # ... 其他初始化

    async def file_operation(self, operation_description: str) -> str:
        """
        文件操作 action(供主 Micro Agent 调用)

        Args:
            operation_description: 操作描述

        Returns:
            str: 操作结果
        """
        result = await self.file_agent.execute(
            task=f"""
            用户要求执行文件操作:{operation_description}

            请解析意图并执行。
            """,
            available_actions=[
                "read_file",
                "write_file",
                "list_directory",
                "search_files",
                "copy_file",
                "move_file",
                "delete_file",
                "all_finished"
            ],
            max_steps=10
        )

        return result
```

## 三、使用示例

### 示例 1: 读取 Dashboard

```python
# 主 Agent 调用
result = await file_operation(
    "读取 overall_dashboard.md 的内容"
)
```

### 示例 2: 创建新章节

```python
result = await file_operation(
    """
    在 Notebook 目录下创建新文件 "第四章 数据分析.md",
    内容为:
    # 第四章 数据分析

    本章将介绍数据分析的方法和工具。
    """
)
```

### 示例 3: 搜索包含特定内容的文件

```python
result = await file_operation(
    "在 Notebook 目录下搜索所有包含'机器学习'的文件"
)
```

### 示例 4: 列出目录

```python
result = await file_operation(
    "列出 Notebook 目录下的所有文件"
)
```

## 四、安全考虑

### 4.1 root_dir 限制

- 所有文件操作都被限制在 `root_dir` 内
- 即使 LLM 被欺骗,也无法访问系统其他部分

### 4.2 使用建议

1. **生产环境**: 使用专用的 workspace 目录作为 root_dir
2. **测试环境**: 可以使用临时目录 (TemporaryDirectory)
3. **沙箱**: 考虑使用 Docker 容器或 chroot 进一步隔离

### 4.3 权限控制

```python
# 可以进一步限制权限
class ReadOnlyFileMicroAgent(FileMicroAgent):
    """只读文件微代理"""

    def _create_action_registry(self) -> dict:
        # 只注册读操作
        registry = super()._create_action_registry()

        # 移除写操作
        for action in ["write_file", "copy_file", "move_file", "delete_file"]:
            registry.pop(action, None)

        return registry
```

## 五、优势总结

✅ **使用成熟工具**: LangChain 社区维护,经过广泛测试
✅ **安全机制完善**: root_dir 限制防止越界访问
✅ **功能丰富**: 支持读、写、搜索等常见操作
✅ **易于扩展**: 可以轻松添加自定义操作
✅ **统一接口**: 主 Agent 只需调用一个 `file_operation` action
✅ **专业化**: File Micro Agent 专注于文件操作,可以优化 prompt

## 六、下一步

1. **安装依赖**: `pip install langchain-community`
2. **实现 FileMicroAgent 类**
3. **集成到 Deep Researcher V2**
4. **测试基本操作**
5. **优化 prompt 提高成功率**

## 七、参考资源

- [LangChain File System 官方文档](https://python.langchain.com/docs/integrations/tools/filesystem/)
- [FileManagementToolkit API 参考](https://reference.langchain.com/v0.3/python/community/agent_toolkits/langchain_community.agent_toolkits.file_management.toolkit.FileManagementToolkit.html)
