"""Vision Skill - 图片查看和分析技能"""

import json
import asyncio
import mimetypes
from ...core.action import register_action


class VisionSkillMixin:
    """Vision Skill Mixin - 提供图片查看能力"""

    _skill_description = """视觉技能。可以查看和分析图片文件内容，支持 PNG、JPEG、GIF、WebP、BMP 等常见图片格式。文件大小限制 10MB。"""

    # 支持的图片 MIME 类型
    _SUPPORTED_MIME_TYPES = {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/bmp"
    }

    # 文件大小限制（10MB）
    _MAX_FILE_SIZE = 10 * 1024 * 1024  # 10,485,760 bytes

    @register_action(
        short_desc="查看图片[file_path]",
        description="查看并分析图片文件内容。支持常见图片格式（PNG, JPEG, GIF, WebP, BMP）。文件大小限制 10MB。",
        param_infos={
            "file_path": "图片文件路径（容器内绝对路径或相对路径）"
        },
    )
    async def look(self, file_path: str) -> str:
        """
        查看图片内容

        返回包含图片数据的特殊 JSON 字符串，
        由 _inject_signal 检测并按 visual_signal 处理

        Args:
            file_path: 图片文件路径

        Returns:
            str: JSON 字符串，包含图片数据和用户消息
        """
        container_session = self.root_agent.container_session

        # 1. 检查文件是否存在
        check_cmd = f"test -f '{file_path}' && echo 'exists' || echo 'not_exists'"
        exit_code, stdout, _ = await asyncio.to_thread(
            container_session.execute, check_cmd
        )

        if exit_code != 0 or stdout.strip() != "exists":
            # 普通错误，返回普通字符串
            return f"查看图片失败：文件不存在\n  路径: {file_path}"

        # 2. 检查文件大小（10MB 限制）
        size_cmd = f"stat -c %s '{file_path}' 2>/dev/null || stat -f %z '{file_path}' 2>/dev/null || echo '0'"
        exit_code, size_stdout, _ = await asyncio.to_thread(
            container_session.execute, size_cmd
        )

        if exit_code == 0:
            try:
                file_size = int(size_stdout.strip())
                if file_size > self._MAX_FILE_SIZE:
                    size_mb = file_size / (1024 * 1024)
                    return f"查看图片失败：文件超过大小限制\n  路径: {file_path}\n  大小: {size_mb:.2f}MB\n  限制: 10MB"
            except ValueError:
                return f"查看图片失败：无法读取文件大小\n  路径: {file_path}"

        # 3. 检测 MIME 类型
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type or mime_type not in self._SUPPORTED_MIME_TYPES:
            # 尝试通过 file 命令检测
            file_cmd = f"file --mime-type '{file_path}' | cut -d' ' -f2"
            exit_code, mime_stdout, _ = await asyncio.to_thread(
                container_session.execute, file_cmd
            )
            if exit_code == 0:
                mime_type = mime_stdout.strip()

        if not mime_type or mime_type not in self._SUPPORTED_MIME_TYPES:
            supported = ", ".join(sorted(self._SUPPORTED_MIME_TYPES))
            return f"查看图片失败：不支持的图片格式\n  路径: {file_path}\n  检测到: {mime_type or '未知'}\n  支持的格式: {supported}"

        # 4. 读取文件并转换为 base64
        base64_cmd = f"base64 -w 0 '{file_path}'"
        exit_code, base64_stdout, stderr = await asyncio.to_thread(
            container_session.execute, base64_cmd
        )

        if exit_code != 0:
            return f"查看图片失败：读取文件失败\n  路径: {file_path}\n  错误: {stderr.strip() if stderr else '(未知错误)'}"

        base64_data = base64_stdout.strip()

        # 5. 构造包含图片数据的返回值
        filename = file_path.split("/")[-1]
        result = {
            "__type__": "visual_result",
            "message": f"已加载图片: {filename}\n  格式: {mime_type}\n  大小: {file_size / 1024:.1f}KB",
            "file_path": file_path,
            "mime_type": mime_type,
            "base64_data": base64_data,
            "size_bytes": file_size,
        }

        # 返回 JSON 字符串，由 _inject_signal 检测并处理
        return json.dumps(result, ensure_ascii=False)
