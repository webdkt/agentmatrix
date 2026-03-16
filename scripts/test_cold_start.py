#!/usr/bin/env python3
"""
Cold Start Test Script - 冷启动测试脚本

验证新的冷启动流程是否正常工作
"""

import os
import shutil
import sys
from pathlib import Path


def test_template_structure():
    """测试模板目录结构"""
    print("🔍 测试模板目录结构...")

    template_dir = Path(__file__).parent.parent / "web" / "matrix_template"

    required_items = [
        ".matrix/configs/agents/User.yml",
        ".matrix/configs/system_config.yml",
        ".matrix/configs/matrix_config.yml",
        ".matrix/database",
        ".matrix/logs",
        ".matrix/sessions",
        "workspace/agent_files",
        "workspace/SKILLS",
        "README.md"
    ]

    all_ok = True
    for item in required_items:
        item_path = template_dir / item
        if item_path.exists():
            print(f"  ✅ {item}")
        else:
            print(f"  ❌ {item} (缺失)")
            all_ok = False

    return all_ok


def test_config_files():
    """测试配置文件内容"""
    print("\n🔍 测试配置文件内容...")

    template_dir = Path(__file__).parent.parent / "web" / "matrix_template"

    # 测试 system_config.yml
    system_config = template_dir / ".matrix" / "configs" / "system_config.yml"
    if system_config.exists():
        with open(system_config, 'r') as f:
            content = f.read()
            if 'email_proxy' in content:
                print("  ✅ system_config.yml 格式正确")
            else:
                print("  ❌ system_config.yml 缺少 email_proxy 配置")
                return False
    else:
        print("  ❌ system_config.yml 不存在")
        return False

    # 测试 matrix_config.yml
    matrix_config = template_dir / ".matrix" / "configs" / "matrix_config.yml"
    if matrix_config.exists():
        with open(matrix_config, 'r') as f:
            content = f.read()
            if 'user_agent_name' in content:
                print("  ✅ matrix_config.yml 格式正确")
            else:
                print("  ❌ matrix_config.yml 缺少 user_agent_name 配置")
                return False
    else:
        print("  ❌ matrix_config.yml 不存在")
        return False

    # 测试 User.yml
    user_yml = template_dir / ".matrix" / "configs" / "agents" / "User.yml"
    if user_yml.exists():
        with open(user_yml, 'r') as f:
            content = f.read()
            if '{{USER_NAME}}' in content:
                print("  ✅ User.yml 包含 {{USER_NAME}} 占位符")
            else:
                print("  ⚠️  User.yml 不包含 {{USER_NAME}} 占位符")
    else:
        print("  ❌ User.yml 不存在")
        return False

    return True


def test_server_py_config():
    """测试 server.py 配置路径"""
    print("\n🔍 测试 server.py 配置路径...")

    server_file = Path(__file__).parent.parent / "server.py"
    with open(server_file, 'r') as f:
        content = f.read()

    required_patterns = [
        'system_dir = matrix_world_dir / ".matrix"',
        'configs_dir = system_dir / "configs"',
        'agents_dir = configs_dir / "agents"',
        'system_config_path = configs_dir / "system_config.yml"',
        'matrix_config_path = configs_dir / "matrix_config.yml"',
    ]

    all_ok = True
    for pattern in required_patterns:
        if pattern in content:
            print(f"  ✅ {pattern}")
        else:
            print(f"  ❌ 缺少: {pattern}")
            all_ok = False

    return all_ok


def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n🔍 测试向后兼容性...")

    server_file = Path(__file__).parent.parent / "server.py"
    with open(server_file, 'r') as f:
        content = f.read()

    # 检查 load_user_agent_name 是否支持旧格式
    if 'matrix_world.yml' in content and '向后兼容' in content:
        print("  ✅ load_user_agent_name 支持向后兼容")
        return True
    else:
        print("  ⚠️  可能缺少向后兼容代码")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("🧪 AgentMatrix 冷启动测试")
    print("=" * 60)

    tests = [
        ("模板目录结构", test_template_structure),
        ("配置文件内容", test_config_files),
        ("server.py 配置路径", test_server_py_config),
        ("向后兼容性", test_backward_compatibility),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} 测试失败: {e}")
            results.append((name, False))

    # 打印总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)

    all_passed = True
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
        if not result:
            all_passed = False

    if all_passed:
        print("\n🎉 所有测试通过！冷启动逻辑已正确适配新架构。")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查上述错误。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
