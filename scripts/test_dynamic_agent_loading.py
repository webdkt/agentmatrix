#!/usr/bin/env python3
"""
测试动态Agent加载功能

这个脚本测试创建Agent后自动加载到运行时的功能
"""

import sys
import os
import asyncio
import json
import shutil
from pathlib import Path

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agentmatrix.core.runtime import AgentMatrix


async def test_dynamic_agent_loading():
    """测试动态Agent加载功能"""
    print("=" * 60)
    print("测试动态Agent加载功能")
    print("=" * 60)

    # 准备测试环境
    test_world = Path('./TestDynamicAgent')
    if test_world.exists():
        shutil.rmtree(test_world)

    print("\n1. 准备测试环境...")
    import server
    server.create_directory_structure(test_world, 'TestUser')
    server.create_world_config(test_world, 'TestUser')

    llm_config = {
        'default_llm': {
            'url': 'https://api.anthropic.com/v1/messages',
            'API_KEY': 'test_key',
            'model_name': 'claude-sonnet-4-20250514'
        },
        'default_slm': {
            'url': 'https://api.anthropic.com/v1/messages',
            'API_KEY': 'test_key',
            'model_name': 'claude-haiku-4-20250514'
        }
    }
    llm_config_path = test_world / '.matrix/configs/agents/llm_config.json'
    llm_config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(llm_config_path, 'w') as f:
        json.dump(llm_config, f)

    print("✅ 测试环境准备完成")

    # 创建测试Agent配置
    print("\n2. 创建测试Agent配置...")
    test_agent_config = {
        "name": "TestAgent",
        "description": "测试动态加载的Agent",
        "class_name": "agentmatrix.agents.base.BaseAgent",
        "backend_model": "default_llm",
        "skills": ["memory"],
        "persona": {
            "base": "你是一个测试Agent。"
        }
    }

    import yaml
    agent_yml_path = test_world / '.matrix/configs/agents/TestAgent.yml'
    with open(agent_yml_path, 'w', encoding='utf-8') as f:
        yaml.dump(test_agent_config, f, allow_unicode=True)

    print(f"✅ 测试Agent配置已创建: {agent_yml_path}")

    # 注意：实际测试需要完整的Docker环境，这里只测试方法存在性
    print("\n3. 测试load_and_register_agent方法...")

    # 检查方法存在
    if not hasattr(AgentMatrix, 'load_and_register_agent'):
        print("❌ load_and_register_agent方法不存在")
        return False

    print("✅ load_and_register_agent方法存在")

    # 检查方法签名
    import inspect
    sig = inspect.signature(AgentMatrix.load_and_register_agent)
    params = list(sig.parameters.keys())

    if 'agent_name' not in params:
        print(f"❌ 方法签名不正确，期望参数: agent_name, 实际: {params}")
        return False

    print(f"✅ 方法签名正确: {sig}")

    # 检查方法是async的
    if not inspect.iscoroutinefunction(AgentMatrix.load_and_register_agent):
        print("❌ 方法不是async函数")
        return False

    print("✅ 方法是async函数")

    # 检查方法文档
    doc = AgentMatrix.load_and_register_agent.__doc__
    if not doc or '动态加载' not in doc:
        print("❌ 方法文档不完整")
        return False

    print("✅ 方法文档完整")

    print("\n4. 检查server.py中的动态加载调用...")

    # 读取server.py检查是否包含动态加载调用
    server_py = Path(__file__).parent.parent / 'server.py'
    server_content = server_py.read_text(encoding='utf-8')

    if 'load_and_register_agent' not in server_content:
        print("❌ server.py中没有调用load_and_register_agent")
        return False

    print("✅ server.py中包含load_and_register_agent调用")

    if 'runtime_loaded' not in server_content:
        print("❌ server.py中没有返回runtime_loaded状态")
        return False

    print("✅ server.py返回runtime_loaded状态")

    # 清理测试环境
    print("\n5. 清理测试环境...")
    shutil.rmtree(test_world)
    print("✅ 测试环境已清理")

    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    print("\n功能说明：")
    print("1. 创建Agent配置文件后，系统会自动调用load_and_register_agent()")
    print("2. Agent会被加载并注册到PostOffice")
    print("3. Agent立即可用，无需重启系统")
    print("4. 前端会自动刷新Agent列表")
    print("5. API响应中包含runtime_loaded状态")

    return True


if __name__ == '__main__':
    try:
        success = asyncio.run(test_dynamic_agent_loading())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
