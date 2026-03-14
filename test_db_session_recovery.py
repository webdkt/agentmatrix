#!/usr/bin/env python
"""
测试数据库驱动的 Session 恢复机制

验证：
1. 数据库查询方法工作正常
2. SessionManager 能正确恢复 session
3. 缓存机制正常工作
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.agentmatrix.db.agent_matrix_db import AgentMatrixDB
from src.agentmatrix.core.session_manager import SessionManager


def test_database_query():
    """测试数据库查询方法"""
    print("\n=== 测试 1: 数据库查询方法 ===")

    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        # 初始化数据库
        db_path = os.path.join(temp_dir, ".matrix", "agentmatrix.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db = AgentMatrixDB(db_path)

        # 创建测试邮件对象
        from datetime import datetime, timezone

        class TestEmail:
            def __init__(self):
                self.id = "test-email-001"
                self.sender_session_id = "session-123"
                self.receiver_session_id = "session-456"
                self.sender = "User"
                self.recipient = "Agent"
                self.subject = "Test Subject"
                self.body = "Test Body"
                self.task_id = "test-task"
                self.in_reply_to = None
                self.timestamp = datetime.now(timezone.utc)
                self.metadata = {}

        # 记录邮件
        test_email = TestEmail()
        db.log_email(test_email)

        # 测试查询
        result = db.get_email_by_id("test-email-001")

        if result:
            print(f"✅ 查询成功: email_id={result['id'][:20]}...")
            print(f"   sender_session_id={result['sender_session_id']}")
            assert result['sender_session_id'] == "session-123", "sender_session_id 不匹配"
            print("✅ sender_session_id 验证通过")
        else:
            print("❌ 查询失败: 返回 None")
            return False

        # 测试查询不存在的邮件
        result = db.get_email_by_id("nonexistent-email")
        if result is None:
            print("✅ 不存在的邮件正确返回 None")
        else:
            print("❌ 不存在的邮件应该返回 None")
            return False

        return True

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)


def test_session_manager_cache():
    """测试 SessionManager 缓存机制"""
    print("\n=== 测试 2: SessionManager 缓存 ===")

    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        # 初始化 SessionManager
        session_manager = SessionManager(
            agent_name="TestAgent",
            workspace_root=temp_dir,
            matrix_path=temp_dir
        )

        # 验证缓存初始化
        if hasattr(session_manager, '_email_session_cache'):
            print("✅ _email_session_cache 属性存在")
        else:
            print("❌ _email_session_cache 属性不存在")
            return False

        # 验证旧属性已删除
        if hasattr(session_manager, 'reply_mappings'):
            print("❌ reply_mappings 属性仍然存在（应该已删除）")
            return False
        else:
            print("✅ reply_mappings 属性已删除")

        # 测试缓存更新
        import asyncio
        asyncio.run(session_manager.update_reply_mapping(
            msg_id="test-msg-001",
            session_id="session-123",
            task_id="test-task"
        ))

        if "test-msg-001" in session_manager._email_session_cache:
            print("✅ 缓存更新成功")
        else:
            print("❌ 缓存更新失败")
            return False

        # 测试缓存获取
        cached_session_id = session_manager._email_session_cache.get("test-msg-001")
        if cached_session_id == "session-123":
            print("✅ 缓存读取成功")
        else:
            print("❌ 缓存读取失败")
            return False

        return True

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)


def test_db_query_in_session_manager():
    """测试 SessionManager 中的数据库查询"""
    print("\n=== 测试 3: SessionManager 数据库查询 ===")

    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        # 初始化数据库
        db_path = os.path.join(temp_dir, ".matrix", "agentmatrix.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db = AgentMatrixDB(db_path)

        # 创建测试邮件
        from datetime import datetime, timezone

        class TestEmail:
            def __init__(self):
                self.id = "original-email-001"
                self.sender_session_id = "session-abc"
                self.receiver_session_id = None
                self.sender = "User"
                self.recipient = "Agent"
                self.subject = "Original Email"
                self.body = "Original content"
                self.task_id = "test-task"
                self.in_reply_to = None
                self.timestamp = datetime.now(timezone.utc)
                self.metadata = {}

        original_email = TestEmail()
        db.log_email(original_email)

        # 初始化 SessionManager
        session_manager = SessionManager(
            agent_name="TestAgent",
            workspace_root=temp_dir,
            matrix_path=temp_dir
        )

        # 测试数据库查询方法
        result = session_manager._get_email_from_db("original-email-001")

        if result:
            print(f"✅ SessionManager 数据库查询成功")
            print(f"   找到 session_id: {result['sender_session_id']}")
            assert result['sender_session_id'] == "session-abc", "session_id 不匹配"
            print("✅ session_id 验证通过")
        else:
            print("❌ SessionManager 数据库查询失败")
            return False

        # 测试查询不存在的邮件
        result = session_manager._get_email_from_db("nonexistent-email")
        if result is None:
            print("✅ 查询不存在的邮件正确返回 None")
        else:
            print("❌ 查询不存在的邮件应该返回 None")
            return False

        return True

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)


def main():
    """运行所有测试"""
    print("=" * 60)
    print("数据库驱动 Session 恢复机制测试")
    print("=" * 60)

    tests = [
        ("数据库查询方法", test_database_query),
        ("SessionManager 缓存", test_session_manager_cache),
        ("SessionManager 数据库查询", test_db_query_in_session_manager),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # 打印测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")

    all_passed = all(result for _, result in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
