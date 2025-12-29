#!/usr/bin/env python3
"""
测试新的配置驱动 Loader
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.loader import AgentLoader

def test_loader():
    print("=" * 60)
    print("测试新的配置驱动 Agent Loader")
    print("=" * 60)

    try:
        # 初始化 Loader
        loader = AgentLoader("profiles")
        print("\n✅ Loader 初始化成功\n")

        # 加载所有 Agent
        agents = loader.load_all()

        print(f"\n{'=' * 60}")
        print(f"✅ 成功加载 {len(agents)} 个 Agent:")
        print(f"{'=' * 60}\n")

        for agent_name, agent in agents.items():
            print(f"🤖 Agent: {agent_name}")
            print(f"   描述: {agent.description}")
            print(f"   类型: {type(agent).__name__}")
            print(f"   继承链: {' -> '.join([c.__name__ for c in type(agent).__mro__ if c.__name__ != 'object'])}")

            # 检查 actions_map
            print(f"   能力数量: {len(agent.actions_map)}")
            if len(agent.actions_map) > 0:
                print(f"   主要能力: {', '.join(list(agent.actions_map.keys())[:5])}")

            # 检查特殊属性
            if hasattr(agent, 'browser_adapter'):
                print(f"   ✅ browser_adapter 已初始化")
            if hasattr(agent, 'research_state'):
                print(f"   ✅ research_state 已初始化")
            if hasattr(agent, 'project_board'):
                print(f"   ✅ project_board 已初始化")
            if hasattr(agent, 'on_mail_received'):
                print(f"   ✅ on_mail_received 已初始化")

            print()

        print(f"{'=' * 60}")
        print("🎉 所有测试通过！")
        print(f"{'=' * 60}")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_loader()
    sys.exit(0 if success else 1)
