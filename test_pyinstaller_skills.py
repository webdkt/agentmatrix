#!/usr/bin/env python3
"""
测试 PyInstaller 环境下的技能加载

模拟 PyInstaller 的 sys._MEIPASS 环境，验证技能加载是否正常
"""

import sys
import os
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_skill_loading():
    """测试技能加载功能"""
    print("=" * 60)
    print("技能加载测试")
    print("=" * 60)

    # 检查环境
    if hasattr(sys, 'frozen'):
        print("✅ PyInstaller 打包环境")
        print(f"   sys._MEIPASS: {sys._MEIPASS}")
    else:
        print("ℹ️  开发环境")

    # 导入技能注册表
    try:
        from agentmatrix.skills import SKILL_REGISTRY
        print("✅ SKILL_REGISTRY 导入成功")
    except Exception as e:
        print(f"❌ SKILL_REGISTRY 导入失败: {e}")
        return False

    # 测试一级技能加载
    print("\n" + "=" * 60)
    print("测试一级技能")
    print("=" * 60)

    level1_skills = [
        'agent_admin',
        'base',
        'deep_researcher',
        'email',
        'file',
        'markdown',
        'memory',
        'new_web_search',
        'scheduler',
        'system_admin'
    ]

    failed_skills = []
    for skill_name in level1_skills:
        result = SKILL_REGISTRY.get_skills([skill_name])
        if result.python_mixins:
            print(f"✅ {skill_name}: {len(result.python_mixins)} mixins")
        else:
            print(f"❌ {skill_name}: 加载失败")
            failed_skills.append(skill_name)

    # 测试嵌套技能加载
    print("\n" + "=" * 60)
    print("测试嵌套技能（dotted name）")
    print("=" * 60)

    nested_skills = [
        'new_web_search.deep_reader',
        'memory.memory_reader'
    ]

    for skill_name in nested_skills:
        result = SKILL_REGISTRY.get_skills([skill_name])
        if result.python_mixins:
            print(f"✅ {skill_name}: {len(result.python_mixins)} mixins")
        else:
            print(f"❌ {skill_name}: 加载失败")
            failed_skills.append(skill_name)

    # 测试技能依赖加载
    print("\n" + "=" * 60)
    print("测试技能依赖链")
    print("=" * 60)

    # 测试一个有依赖的技能
    result = SKILL_REGISTRY.get_skills(['new_web_search'])
    if result.python_mixins:
        # 检查 base 依赖是否自动加载
        if 'base' in SKILL_REGISTRY._python_mixins:
            print("✅ 技能依赖自动加载工作正常（base 已加载）")
        else:
            print("⚠️  技能依赖自动加载可能有问题")

    # 检查 agentmatrix.skills 模块的文件路径
    print("\n" + "=" * 60)
    print("检查模块路径")
    print("=" * 60)

    try:
        import agentmatrix.skills
        print(f"agentmatrix.skills.__file__: {agentmatrix.skills.__file__}")

        # 检查嵌套技能文件是否存在
        skills_dir = Path(agentmatrix.skills.__file__).parent
        nested_file = skills_dir / 'new_web_search' / 'deep_reader' / 'skill.py'
        print(f"嵌套技能文件存在: {nested_file.exists()}")
        print(f"嵌套技能路径: {nested_file}")

        # 检查是否在 PyInstaller 的 MEIPASS 中
        if hasattr(sys, '_MEIPASS'):
            meipass_nested = Path(sys._MEIPASS) / 'agentmatrix' / 'skills' / 'new_web_search' / 'deep_reader' / 'skill.py'
            print(f"MEIPASS 中的嵌套技能: {meipass_nested}")
            print(f"MEIPASS 文件存在: {meipass_nested.exists()}")

    except Exception as e:
        print(f"❌ 模块路径检查失败: {e}")

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    if failed_skills:
        print(f"❌ 失败的技能 ({len(failed_skills)}): {', '.join(failed_skills)}")
        return False
    else:
        print("✅ 所有技能加载测试通过")
        return True

if __name__ == "__main__":
    success = test_skill_loading()
    sys.exit(0 if success else 1)
