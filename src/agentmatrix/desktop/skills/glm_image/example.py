"""
GLM Image Skill 使用示例

这个示例展示了如何使用 glm_image skill 来生成图像。
"""

import asyncio
import os


async def example_usage():
    """使用示例"""
    from agentmatrix.skills.glm_image import Glm_imageSkillMixin

    # 创建一个简单的 Agent 类来混入 skill
    class MockAgent:
        root_agent = None

    class MyAgent(MockAgent, Glm_imageSkillMixin):
        pass

    # 检查环境变量
    api_key = os.getenv("GLM_API_KEY")
    if not api_key:
        print("❌ 请先设置环境变量 GLM_API_KEY")
        print("   export GLM_API_KEY='your-api-key'")
        return

    # 创建 agent 实例
    agent = MyAgent()

    # 生成图像
    try:
        print("🎨 正在生成图像...")
        result = await agent.generate_image("一只可爱的小猫咪，坐在阳光明媚的窗台上，背景是蓝天白云")
        print(f"✅ 图像生成成功！")
        print(f"📁 返回的容器内路径: {result}")
        print(f"💡 提示: 在容器环境中，图像实际保存在宿主机的对应目录")
    except Exception as e:
        print(f"❌ 生成失败: {e}")


if __name__ == "__main__":
    asyncio.run(example_usage())
