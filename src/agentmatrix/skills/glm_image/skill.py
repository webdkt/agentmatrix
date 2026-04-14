"""
GLM Image Skill - 智谱图像生成技能

使用智谱 AI 的图像生成 API 创建高质量图像。
"""

import os
import asyncio
from pathlib import Path
from datetime import datetime

import aiohttp

from ...core.action import register_action


class Glm_imageSkillMixin:
    """智谱图像生成技能"""

    _skill_description = "智谱图像生成技能：使用智谱 AI 的 GLM-Image 模型从文本提示生成高质量图像"

    @register_action(
        short_desc="[prompt]",
        description="使用智谱 AI 的图像生成 API 从文本描述生成高质量图像。生成的图像将保存在 ~/current_task/tmp/ 目录下。",
        param_infos={
            "prompt": "图像的自然语言描述，例如：一只可爱的小猫咪，坐在阳光明媚的窗台上，背景是蓝天白云"
        },
    )
    async def generate_image(self, prompt: str) -> str:
        """
        生成图像

        Args:
            prompt: 图像的自然语言描述

        Returns:
            容器内路径（如 ~/current_task/tmp/glm_image_20260414_091345.png）

        Raises:
            ValueError: 如果未设置 GLM_API_KEY 环境变量
            RuntimeError: 如果 API 调用失败
        """
        # 从环境变量获取 API key
        api_key = os.getenv("GLM_API_KEY")
        if not api_key:
            raise ValueError("未设置环境变量 GLM_API_KEY，请先设置 API key")

        # 获取 root_agent 和 runtime 信息
        root_agent = self.root_agent

        # 准备请求
        url = "https://open.bigmodel.cn/api/paas/v4/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "glm-image",
            "prompt": prompt,
            "size": "1280x1280",
            "quality": "hd"
        }

        # 调用 API
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"API 调用失败 (status {response.status}): {error_text}")

                result = await response.json()

                # 提取图片 URL
                try:
                    image_url = result["data"][0]["url"]
                except (KeyError, IndexError) as e:
                    raise RuntimeError(f"API 响应格式错误: {result}")

                # 确定保存路径
                # 检查是否有 runtime（Docker 环境）
                if hasattr(root_agent, "runtime") and root_agent.runtime:
                    # Docker 环境：保存到宿主机路径
                    runtime = root_agent.runtime
                    agent_name = root_agent.name
                    task_id = root_agent.current_task_id or "default"

                    # 宿主机路径：workspace/agent_files/{agent_name}/work_files/{task_id}/tmp/
                    host_output_dir = runtime.paths.get_agent_work_files_dir(agent_name, task_id) / "tmp"
                    host_output_dir.mkdir(parents=True, exist_ok=True)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"glm_image_{timestamp}.png"
                    host_filepath = host_output_dir / filename

                    # 下载并保存图片到宿主机
                    async with session.get(image_url) as img_response:
                        if img_response.status != 200:
                            raise RuntimeError(f"图片下载失败 (status {img_response.status})")

                        content = await img_response.read()
                        host_filepath.write_bytes(content)

                    # 返回容器内路径
                    container_path = f"~/current_task/tmp/{filename}"
                    return container_path
                else:
                    # 非 Docker 环境：直接保存到本地路径
                    output_dir = Path.home() / "current_task" / "tmp"
                    output_dir.mkdir(parents=True, exist_ok=True)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"glm_image_{timestamp}.png"
                    filepath = output_dir / filename

                    async with session.get(image_url) as img_response:
                        if img_response.status != 200:
                            raise RuntimeError(f"图片下载失败 (status {img_response.status})")

                        content = await img_response.read()
                        filepath.write_bytes(content)

                    return f"~/current_task/tmp/{filename}"
