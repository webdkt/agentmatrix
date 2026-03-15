#!/usr/bin/env python3
"""
回复链测试 - 模拟多轮对话

测试场景：
1. User发送邮件1给Agent
2. Agent回复邮件2（回复邮件1）
3. User发送邮件3（回复邮件1，连续发送）
4. Agent回复邮件4（回复邮件3）

验证：
- 所有邮件的receiver_session_id都正确
- session目录结构正确
- reply_mapping正确工作
"""

import sys
import os
import asyncio
import json
import shutil
import yaml
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agentmatrix.core.session_manager import SessionManager
from agentmatrix.core.message import Email
from agentmatrix.db.agent_matrix_db import AgentMatrixDB


async def test_reply_chain():
    """测试回复链"""
    print("=" * 70)
    print("回复链测试 - 模拟多轮对话")
    print("=" * 70)

    # 创建测试环境
    test_world = Path('./TestReplyChain')
    if test_world.exists():
        shutil.rmtree(test_world)

    # 初始化环境
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import server
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    server.create_directory_structure(test_world, 'TestUser')
    server.create_world_config(test_world, 'TestUser')

    # 创建LLM配置
    llm_config = {
        'default_llm': {
            'url': 'mock://llm',
            'API_KEY': 'mock_key',
            'model_name': 'mock-model'
        },
        'default_slm': {
            'url': 'mock://slm',
            'API_KEY': 'mock_key',
            'model_name': 'mock-slm'
        }
    }

    llm_config_path = test_world / '.matrix/configs/agents/llm_config.json'
    with open(llm_config_path, 'w') as f:
        json.dump(llm_config, f, indent=2)

    print(f"✅ 测试环境已创建")

    # 创建User Agent
    user_config = {
        'name': 'User',
        'description': 'Test User',
        'class_name': 'agentmatrix.agents.user_proxy.UserProxyAgent',
        'backend_model': 'default_llm',
        'mixins': ['skills.filesystem.FileSkillMixin'],
        'attribute_initializations': {'on_mail_received': None}
    }

    user_yml = test_world / '.matrix/configs/agents/User.yml'
    with open(user_yml, 'w', encoding='utf-8') as f:
        yaml.dump(user_config, f, allow_unicode=True)

    # 创建Agent
    agent_config = {
        'name': 'Agent',
        'description': 'Test Agent',
        'class_name': 'agentmatrix.agents.base.BaseAgent',
        'backend_model': 'default_llm',
        'skills': ['memory'],
        'persona': {'base': '你是一个测试Agent。'}
    }

    agent_yml = test_world / '.matrix/configs/agents/Agent.yml'
    with open(agent_yml, 'w', encoding='utf-8') as f:
        yaml.dump(agent_config, f, allow_unicode=True)

    print(f"✅ Agents已创建")

    # 创建SessionManager
    session_mgr = SessionManager(
        agent_name='Agent',
        matrix_path=str(test_world)
    )

    db = AgentMatrixDB(str(test_world / '.matrix/database/agentmatrix.db'))

    # 获取一个共同的task_id
    task_id = str(uuid4())

    print(f"\n📧 邮件流程测试")
    print(f"Task ID: {task_id[:8]}...")

    # 邮件1: User -> Agent (初始邮件)
    user_session_id = str(uuid4())
    email1 = Email(
        sender='User',
        recipient='Agent',
        subject='Question 1',
        body='What is AI?',
        task_id=task_id,
        sender_session_id=user_session_id,
        receiver_session_id=None
    )

    print(f"\n1️⃣ 邮件1: {email1.sender} -> {email1.recipient}")
    print(f"   Subject: {email1.subject}")
    print(f"   Sender Session: {user_session_id[:8]}...")
    print(f"   Receiver Session: None (初始邮件)")

    # 处理邮件1
    session1 = await session_mgr.get_session(email1)
    db.log_email(email1)
    db.update_receiver_session(email1.id, session1['session_id'], 'Agent')

    print(f"   ✅ Session创建: {session1['session_id'][:8]}...")
    print(f"   ✅ Receiver Session已更新")

    # 更新reply_mapping
    await session_mgr.update_reply_mapping(email1.id, session1['session_id'], task_id)
    print(f"   ✅ Reply mapping已更新: {email1.id[:8]}... -> {session1['session_id'][:8]}...")

    # 邮件2: Agent -> User (回复邮件1)
    email2 = Email(
        sender='Agent',
        recipient='User',
        subject='Re: Question 1',
        body='AI is artificial intelligence.',
        in_reply_to=email1.id,
        task_id=task_id,
        sender_session_id=session1['session_id'],
        receiver_session_id=user_session_id
    )

    print(f"\n2️⃣ 邮件2: {email2.sender} -> {email2.recipient}")
    print(f"   Subject: {email2.subject}")
    print(f"   In Reply To: {email2.in_reply_to[:8]}...")
    print(f"   Sender Session: {email2.sender_session_id[:8]}...")
    print(f"   Receiver Session: {email2.receiver_session_id[:8]}...")

    db.log_email(email2)
    print(f"   ✅ 邮件已插入数据库")

    # 更新reply_mapping
    await session_mgr.update_reply_mapping(email2.id, session1['session_id'], task_id)
    print(f"   ✅ Reply mapping已更新: {email2.id[:8]}... -> {session1['session_id'][:8]}...")

    # 邮件3: User -> Agent (回复邮件1，连续发送)
    email3 = Email(
        sender='User',
        recipient='Agent',
        subject='Re: Question 1',
        body='Can you explain more?',
        in_reply_to=email1.id,
        task_id=task_id,
        sender_session_id=user_session_id,
        receiver_session_id=session1['session_id']
    )

    print(f"\n3️⃣ 邮件3: {email3.sender} -> {email3.recipient}")
    print(f"   Subject: {email3.subject}")
    print(f"   In Reply To: {email3.in_reply_to[:8]}...")
    print(f"   Sender Session: {email3.sender_session_id[:8]}...")
    print(f"   Receiver Session: {email3.receiver_session_id[:8]}... (应该恢复session)")

    # 处理邮件3 - 测试session恢复
    session3 = await session_mgr.get_session(email3)
    print(f"   ✅ Session已恢复: {session3['session_id'][:8]}...")

    # 验证session是否正确恢复
    if session3['session_id'] == session1['session_id']:
        print(f"   ✅ Session正确恢复（使用原来的session）")
    else:
        print(f"   ❌ Session错误（创建了新session）")
        print(f"      期望: {session1['session_id'][:8]}...")
        print(f"      实际: {session3['session_id'][:8]}...")

    db.log_email(email3)
    db.update_receiver_session(email3.id, session3['session_id'], 'Agent')

    # 邮件4: Agent -> User (回复邮件3)
    email4 = Email(
        sender='Agent',
        recipient='User',
        subject='Re: Question 1',
        body='Sure! AI is...',
        in_reply_to=email3.id,
        task_id=task_id,
        sender_session_id=session1['session_id'],
        receiver_session_id=user_session_id
    )

    print(f"\n4️⃣ 邮件4: {email4.sender} -> {email4.recipient}")
    print(f"   Subject: {email4.subject}")
    print(f"   In Reply To: {email4.in_reply_to[:8]}...")
    print(f"   Sender Session: {email4.sender_session_id[:8]}...")
    print(f"   Receiver Session: {email4.receiver_session_id[:8]}...")

    db.log_email(email4)
    print(f"   ✅ 邮件已插入数据库")

    # 验证结果
    print(f"\n" + "=" * 70)
    print("验证结果")
    print("=" * 70)

    # 查询数据库
    import sqlite3
    conn = sqlite3.connect(str(test_world / '.matrix/database/agentmatrix.db'))
    cursor = conn.cursor()

    cursor.execute('SELECT id, sender, recipient, sender_session_id, receiver_session_id, in_reply_to FROM emails ORDER BY timestamp')
    emails = cursor.fetchall()

    print(f"\n📊 数据库中的 {len(emails)} 封邮件:")
    for i, email in enumerate(emails, 1):
        id_val, sender, recipient, sender_sid, receiver_sid, in_reply_to = email
        print(f"\n{i}. {sender} -> {recipient}")
        print(f"   ID: {id_val[:8]}...")
        print(f"   Sender Session: {sender_sid[:8] if sender_sid else 'None'}...")
        print(f"   Receiver Session: {receiver_sid[:8] if receiver_sid else 'None'}...")
        print(f"   In Reply To: {in_reply_to[:8] if in_reply_to else 'None'}...")

    # 验证回复链正确性
    print(f"\n🔍 验证回复链:")
    errors = []

    for email in emails:
        id_val, sender, recipient, sender_sid, receiver_sid, in_reply_to = email

        if in_reply_to:
            # 查找被回复的邮件
            cursor.execute('SELECT sender_session_id FROM emails WHERE id = ?', (in_reply_to,))
            result = cursor.fetchone()

            if result and result[0]:
                original_sender_sid = result[0]

                if receiver_sid == original_sender_sid:
                    print(f"   ✅ {id_val[:8]}: Receiver Session正确")
                else:
                    print(f"   ❌ {id_val[:8]}: Receiver Session错误!")
                    print(f"      期望: {original_sender_sid[:8]}...")
                    print(f"      实际: {receiver_sid[:8] if receiver_sid else 'None'}...")
                    errors.append((id_val, receiver_sid, original_sender_sid))

    conn.close()

    # 验证session目录
    print(f"\n📁 验证Session目录:")
    sessions_dir = test_world / '.matrix/sessions/Agent'
    if sessions_dir.exists():
        task_dirs = list(sessions_dir.iterdir())
        for task_dir in task_dirs:
            if task_dir.is_dir():
                history_dir = task_dir / 'history'
                if history_dir.exists():
                    session_dirs = list(history_dir.iterdir())
                    print(f"   ✅ Task {task_dir.name[:8]}: {len(session_dirs)} sessions")
                    for session_dir in session_dirs:
                        if session_dir.is_dir():
                            history_file = session_dir / 'history.json'
                            print(f"      {session_dir.name[:8]}... - {'✅' if history_file.exists() else '❌'}")
                else:
                    print(f"   ❌ Task {task_dir.name}: history目录不存在")
    else:
        print(f"   ❌ Sessions目录不存在")
        errors.append("No sessions directory")

    # 清理
    if hasattr(db, 'conn') and db.conn:
        db.conn.close()

    shutil.rmtree(test_world)
    print(f"\n✅ 测试环境已清理")

    # 返回测试结果
    if errors:
        print(f"\n❌ 发现 {len(errors)} 个错误:")
        for error in errors:
            print(f"   {error}")
        return False
    else:
        print(f"\n✅ 所有测试通过！回复链完全正确！")
        return True


if __name__ == '__main__':
    try:
        success = asyncio.run(test_reply_chain())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
