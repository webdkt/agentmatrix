"""
测试动态 finish_task 参数功能

这个测试展示了新的 result_params 功能
"""

import asyncio
import sys
from pathlib import Path

# 添加 src 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentmatrix.agents.micro_agent import MicroAgent, finish_task


class MockBrain:
    """模拟 Brain（LLM 接口）"""
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    async def think(self, messages):
        """返回预设的响应"""
        response = self.responses[self.call_count]
        self.call_count += 1
        return response


class MockCerebellum:
    """模拟 Cerebellum（参数协商器）"""
    async def negotiate(self, initial_intent, tools_manifest, contacts, brain_callback):
        # 简单模拟：总是返回 READY，带解析好的参数
        return {
            "action": "finish_task",
            "params": {"result": "Test completed"}
        }

    async def parse_action_params(self, intent, action_name, param_schema, brain_callback):
        """模拟新的参数解析方法"""
        # 简单模拟：总是返回 READY，带解析好的参数
        return {
            "action": action_name,
            "params": {"result": "Test completed"}
        }

    async def think(self, messages):
        return {"reply": "", "reasoning": ""}


async def test_simple_mode():
    """测试简单模式（向后兼容）"""
    print("=" * 60)
    print("测试 1: 简单模式（向后兼容）")
    print("=" * 60)

    # 准备 Mock Brain
    brain = MockBrain([
        # 第 1 次 think: LLM 决定调用 finish_task
        {
            "reply": "I'll finish this task now with finish_task(result='Test completed')",
            "reasoning": "Task is simple, I can finish it."
        }
    ])

    cerebellum = MockCerebellum()

    # 创建 Micro Agent
    agent = MicroAgent(
        brain=brain,
        cerebellum=cerebellum,
        action_registry={},
        name="TestAgent"
    )

    # 执行（不传 result_params，应该返回字符串）
    result = await agent.execute(
        persona="You are a test assistant.",
        task="Say hello",
        available_actions=["finish_task"]
    )

    print(f"返回类型: {type(result)}")
    print(f"返回值: {result}")
    print(f"✅ 简单模式通过：返回字符串\n")


async def test_structured_mode():
    """测试结构化模式（新功能）"""
    print("=" * 60)
    print("测试 2: 结构化模式（新功能）")
    print("=" * 60)

    # 准备 Mock Brain
    brain = MockBrain([
        {
            "reply": "I'll analyze and return structured results with finish_task(summary='Analysis done', issues=['bug1', 'bug2'], score=85)",
            "reasoning": "Completing analysis with structured output."
        }
    ])

    # 模拟 Cerebellum 返回结构化参数
    class MockCerebellumStructured:
        async def negotiate(self, initial_intent, tools_manifest, contacts, brain_callback):
            return {
                "action": "finish_task",
                "params": {
                    "summary": "Analysis done",
                    "issues": ["bug1", "bug2"],
                    "score": 85
                }
            }

        async def parse_action_params(self, intent, action_name, param_schema, brain_callback):
            """模拟新的参数解析方法"""
            return {
                "action": action_name,
                "params": {
                    "summary": "Analysis done",
                    "issues": ["bug1", "bug2"],
                    "score": 85
                }
            }

        async def think(self, messages):
            return {"reply": "", "reasoning": ""}

    cerebellum = MockCerebellumStructured()

    # 创建 Micro Agent
    agent = MicroAgent(
        brain=brain,
        cerebellum=cerebellum,
        action_registry={},
        name="TestAgent"
    )

    # 执行（传入 result_params，应该返回字典）
    result = await agent.execute(
        persona="You are a code reviewer.",
        task="Review this code",
        available_actions=["finish_task"],
        result_params={
            "summary": "审查总结",
            "issues": "问题列表",
            "score": "评分 (0-100)"
        }
    )

    print(f"返回类型: {type(result)}")
    print(f"返回值: {result}")
    print(f"✅ 结构化模式通过：返回字典")
    print(f"   - summary: {result['summary']}")
    print(f"   - issues: {result['issues']}")
    print(f"   - score: {result['score']}\n")


async def test_finish_task_metadata():
    """测试 finish_task 元数据动态更新"""
    print("=" * 60)
    print("测试 3: finish_task 元数据动态更新")
    print("=" * 60)

    # 准备 Mock Brain（立即返回 finish_task）
    brain = MockBrain([
        {
            "reply": "I'll finish now",
            "reasoning": "Done."
        }
    ])

    cerebellum = MockCerebellum()

    # 创建 Micro Agent
    agent = MicroAgent(
        brain=brain,
        cerebellum=cerebellum,
        action_registry={},
        name="TestAgent"
    )

    # 测试动态更新（通过 execute() 的 result_params）
    print("\n3.1 动态更新元数据:")
    result = await agent.execute(
        persona="You are a tester.",
        task="Test",
        available_actions=[],
        result_params={
            "summary": "总结内容",
            "issues": "问题列表",
            "score": "评分 (0-100)"
        }
    )

    # 检查元数据是否被正确更新
    print(f"   更新后参数描述: {finish_task._action_param_infos}")
    print(f"   更新后 Action 描述: {finish_task._action_desc}")

    assert finish_task._action_param_infos == {
        "summary": "总结内容",
        "issues": "问题列表",
        "score": "评分 (0-100)"
    }
    assert "总结内容" in finish_task._action_desc
    assert "问题列表" in finish_task._action_desc
    assert "评分 (0-100)" in finish_task._action_desc
    assert "需要提供：" in finish_task._action_desc

    # 测试再次执行不带 result_params，应该恢复默认值
    print("\n3.2 恢复默认模式:")
    brain2 = MockBrain([
        {
            "reply": "Done",
            "reasoning": "OK"
        }
    ])

    agent2 = MicroAgent(
        brain=brain2,
        cerebellum=MockCerebellum(),
        action_registry={},
        name="TestAgent2"
    )

    result2 = await agent2.execute(
        persona="You are a tester.",
        task="Test2",
        available_actions=[]
        # 不传 result_params
    )

    print(f"   恢复后参数描述: {finish_task._action_param_infos}")
    print(f"   恢复后 Action 描述: {finish_task._action_desc}")

    assert finish_task._action_param_infos == {"result": "最终结果的描述（可选）"}
    assert "需要提供：" not in finish_task._action_desc

    print(f"\n✅ 元数据动态更新测试通过\n")


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("动态 finish_task 参数功能测试")
    print("=" * 60 + "\n")

    try:
        await test_simple_mode()
        await test_structured_mode()
        await test_finish_task_metadata()

        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
