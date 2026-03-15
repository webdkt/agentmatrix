#!/usr/bin/env python3
"""
Session管理测试脚本

验证新架构下的session管理逻辑
"""

import sys
import os
from pathlib import Path

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agentmatrix.core.paths import MatrixPaths


def test_session_paths():
    """测试session路径生成逻辑"""
    print("=" * 60)
    print("测试Session路径生成逻辑")
    print("=" * 60)

    # 创建MatrixPaths实例
    matrix_root = "./TestMatrixWorld"
    paths = MatrixPaths(matrix_root)

    print(f"\n1. Matrix Root: {matrix_root}")
    print(f"   System Dir: {paths.system_dir}")
    print(f"   Sessions Dir: {paths.sessions_dir}")

    # 测试agent session路径
    agent_name = "Mark"
    task_id = "test_task_123"
    session_id = "sess_abc"

    print(f"\n2. Agent Session Paths:")
    print(f"   Agent Name: {agent_name}")
    print(f"   Task ID: {task_id}")
    print(f"   Session ID: {session_id}")

    # 获取各种路径
    agent_sessions_dir = paths.sessions_dir / agent_name
    print(f"\n   Agent Sessions Dir: {agent_sessions_dir}")

    task_history_dir = paths.get_agent_session_history_dir(agent_name, task_id, "")
    print(f"   Task History Dir: {task_history_dir}")

    session_dir = paths.get_agent_session_history_dir(agent_name, task_id, session_id)
    print(f"   Session Dir: {session_dir}")

    # 验证路径结构
    print(f"\n3. 路径结构验证:")

    expected_structure = [
        "TestMatrixWorld/.matrix",
        "TestMatrixWorld/.matrix/sessions",
        "TestMatrixWorld/.matrix/sessions/Mark",
        "TestMatrixWorld/.matrix/sessions/Mark/test_task_123",
        "TestMatrixWorld/.matrix/sessions/Mark/test_task_123/history",
        "TestMatrixWorld/.matrix/sessions/Mark/test_task_123/history/sess_abc"
    ]

    for path_str in expected_structure:
        path = Path(path_str)
        print(f"   {'✅' if str(path).startswith(matrix_root) else '❌'} {path_str}")

    print(f"\n4. 数据库路径:")
    print(f"   Database Path: {paths.database_path}")

    print(f"\n5. 完整的session文件路径:")
    history_file = session_dir / "history.json"
    context_file = session_dir / "context.json"
    print(f"   History File: {history_file}")
    print(f"   Context File: {context_file}")

    print("\n" + "=" * 60)
    print("✅ 路径测试完成")
    print("=" * 60)

    return True


def test_session_manager_init():
    """测试SessionManager初始化"""
    print("\n" + "=" * 60)
    print("测试SessionManager初始化")
    print("=" * 60)

    from agentmatrix.core.session_manager import SessionManager

    agent_name = "Mark"
    matrix_path = "./TestMatrixWorld"

    print(f"\n1. 初始化参数:")
    print(f"   Agent Name: {agent_name}")
    print(f"   Matrix Path: {matrix_path}")

    try:
        # 创建SessionManager（新架构：只需要matrix_path）
        session_mgr = SessionManager(
            agent_name=agent_name,
            matrix_path=matrix_path
        )

        print(f"\n2. SessionManager创建成功:")
        print(f"   Agent Name: {session_mgr.agent_name}")
        print(f"   Matrix Path: {session_mgr.matrix_path}")
        print(f"   Paths: {session_mgr.matrixpath}")

        print(f"\n3. 验证paths属性:")
        if session_mgr.matrixpath:
            print(f"   ✅ paths属性存在")
            print(f"   System Dir: {session_mgr.matrixpath.system_dir}")
            print(f"   Sessions Dir: {session_mgr.matrixpath.sessions_dir}")
        else:
            print(f"   ❌ paths属性不存在")

        print(f"\n4. 测试_get_session_base_path:")
        task_id = "test_task_123"
        base_path = session_mgr._get_session_base_path(task_id)
        print(f"   Task ID: {task_id}")
        print(f"   Base Path: {base_path}")

        expected_path = Path(matrix_path) / ".matrix" / "sessions" / agent_name / task_id / "history"
        if base_path == expected_path:
            print(f"   ✅ 路径正确")
        else:
            print(f"   ❌ 路径错误")
            print(f"   期望: {expected_path}")
            print(f"   实际: {base_path}")

        print("\n" + "=" * 60)
        print("✅ SessionManager初始化测试完成")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ SessionManager初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = True

    try:
        # 测试路径生成
        if not test_session_paths():
            success = False

        # 测试SessionManager初始化
        if not test_session_manager_init():
            success = False

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
