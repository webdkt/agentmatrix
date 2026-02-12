"""
工作上下文 - 为 MicroAgent 提供类似文件系统的目录层级
"""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class WorkingContext:
    """工作上下文

    提供类似文件系统的层级结构：
    - base_dir: 根目录（通常是 Agent.session_folder）
    - current_dir: 当前工作目录
    - context_stack: 调用栈（用于追踪和调试）
    """
    base_dir: str
    current_dir: str
    context_stack: List[str] = field(default_factory=list)

    def create_child(self, label: str, use_timestamp: bool = True) -> 'WorkingContext':
        """创建子上下文（在当前目录下创建子目录）

        Args:
            label: 子目录名称（通常是 run_label）
            use_timestamp: 是否添加时间戳
                - True: {label}_YYYYMMDD_HHMMSS（默认，适合独立任务）
                - False: {label}（适合多轮共享目录）

        Returns:
            新的 WorkingContext 实例
        """
        if use_timestamp:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_label = f"{label}_{timestamp}"
        else:
            safe_label = label

        # 清理特殊字符
        safe_label = safe_label.replace("/", "_").replace("\\", "_")

        child_dir = os.path.join(self.current_dir, safe_label)
        os.makedirs(child_dir, exist_ok=True)

        # 创建子上下文
        return WorkingContext(
            base_dir=self.base_dir,
            current_dir=child_dir,
            context_stack=self.context_stack + [safe_label]
        )

    def get_relative_path(self, path: str = None) -> str:
        """获取相对于 base_dir 的路径

        Args:
            path: 可选的路径，如果为 None 则使用 current_dir

        Returns:
            相对路径（如 "web_search_1/file_operation"）
        """
        target = path or self.current_dir
        return os.path.relpath(target, self.base_dir)

    def __str__(self) -> str:
        """字符串表示（用于日志）"""
        if self.context_stack:
            return f"WorkingContext({'/'.join(self.context_stack)})"
        return f"WorkingContext(root)"
