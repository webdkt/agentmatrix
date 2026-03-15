#!/usr/bin/env python3
"""
最终验证测试 - 完整的邮件回复链测试

验证修复后的新架构是否正常工作
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


async def final_test():
    """最终验证测试"""
    print("=" * 70)
    print("最终验证测试 - 完整邮件回复链")
    print("=" * 70)

    # 创建测试环境
    test_world = Path('./FinalTestWorld')
    if test_world.exists():
        shutil.rmtree(test_world)

    # 初始化环境
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import server
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    server.create_directory_structure(test_world, 'User')
    server.create_world_config(test_world, 'User')

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

    # 创建两个SessionManager（模拟User和Agent）
    user_session_mgr = SessionManager(
        agent_name='User',
        matrix_path=str(test_world)
    )

    agent_session_mgr = SessionManager(
        agent_name='Agent',
        matrix_path=str(test_world)
    )

    db = AgentMatrixDB(str(test_world / '.matrix/database/agentmatrix.db'))

    # 获取一个共同的task_id
    task_id = str(uuid4())
    user_session_id = str(uuid4())
    agent_session_id = str(uuid4())

    print(f"\n📧 完整对话流程测试")
    print(f"Task ID: {task_id[:8]}...")
    print(f"User Session: {user_session_id[:8]}...")
    print(f"Agent Session: {agent_session_id[:8]}...")

    # 邮件1：User -> Agent
    email1 = Email(
        sender='User',
        recipient='Agent',
        subject='Hello',
        body='Hi Agent!',
        task_id=task_id,
        sender_session_id=user_session_id,
        receiver_session_id=None
    )

    print(f"\n1️⃣ 邮件1: User -> Agent")
    print(f"   Sender Session: {email1.sender_session_id[:8]}...")
    print(f"   Receiver Session: None")

    # Agent接收邮件1
    session1 = await agent_session_mgr.get_session(email1)
    db.log_email(email1)
    db.update_receiver_session(email1.id, session1['session_id'], 'Agent')
    await agent_session_mgr.update_reply_mapping(email1.id, session1['session_id'], task_id)

    print(f"   ✅ Agent Session: {session1['session_id'][:8]}...")
    print(f"   📁 Session目录: {test_world}/.matrix/sessions/Agent/{task_id[:8]}.../history/{session1['session_id'][:8]}...")

    # 邮件2：Agent -> User (回复邮件1)
    email2 = Email(
        sender='Agent',
        recipient='User',
        subject='Re: Hello',
        body='Hi User!',
        in_reply_to=email1.id,
        task_id=task_id,
        sender_session_id=session1['session_id'],
        receiver_session_id=user_session_id
    )

    print(f"\n2️⃣ 邮件2: Agent -> User (回复邮件1)")
    print(f"   In Reply To: {email2.in_reply_to[:8]}...")
    print(f"   Sender Session: {email2.sender_session_id[:8]}... (Agent)")
    print(f"   Receiver Session: {email2.receiver_session_id[:8]}... (User)")

    db.log_email(email2)
    await agent_session_mgr.update_reply_mapping(email2.id, session1['session_id'], task_id)

    # 邮件3：User -> Agent (回复邮件1，连续发送)
    email3 = Email(
        sender='User',
        recipient='Agent',
        subject='Re: Hello',
        body='How are you?',
        in_reply_to=email1.id,
        task_id=task_id,
        sender_session_id=user_session_id,
        receiver_session_id=None  # 让Agent接收后更新
    )

    print(f"\n3️⃣ 邮件3: User -> Agent (回复邮件1)")
    print(f"   In Reply To: {email3.in_reply_to[:8]}...")
    print(f"   Sender Session: {email3.sender_session_id[:8]}... (User)")
    print(f"   Receiver Session: None (让Agent接收后更新)")

    # Agent接收邮件3 - 关键测试：能否恢复session1？
    session3 = await agent_session_mgr.get_session(email3)
    db.log_email(email3)
    db.update_receiver_session(email3.id, session3['session_id'], 'Agent')

    print(f"   ✅ Agent Session: {session3['session_id'][:8]}...")

    # 验证：session3应该等于session1（恢复的session）
    if session3['session_id'] == session1['session_id']:
        print(f"   ✅ Session正确恢复！")
    else:
        print(f"   ❌ Session错误：期望={session1['session_id'][:8]}..., 实际={session3['session_id'][:8]}...")
        return False

    # 邮件4：Agent -> User (回复邮件3)
    email4 = Email(
        sender='Agent',
        recipient='User',
        subject='Re: Hello',
        body='I am fine!',
        in_reply_to=email3.id,
        task_id=task_id,
        sender_session_id=session1['session_id'],
        receiver_session_id=user_session_id
    )

    print(f"\n4️⃣ 邮件4: Agent -> User (回复邮件3)")
    print(f"   In Reply To: {email4.in_reply_to[:8]}...")
    db.log_email(email4)
    await agent_session_mgr.update_reply_mapping(email4.id, session1['session_id'], task_id)

    # 验证结果
    print(f"\n" + "=" * 70)
    print("验证结果")
    print("=" * 70)

    import sqlite3
    conn = sqlite3.connect(str(test_world / '.matrix/database/agentmatrix.db'))
    cursor = conn.cursor()

    cursor.execute('SELECT id, sender, recipient, sender_session_id, receiver_session_id, in_reply_to FROM emails ORDER BY timestamp')
    emails = cursor.fetchall()

    print(f"\n📊 数据库记录 (共{len(emails)}封邮件):")
    for i, email in enumerate(emails, 1):
        id_val, sender, recipient, sender_sid, receiver_sid, in_reply_to = email
        print(f"\n{i}. {sender} -> {recipient}")
        print(f"   ID: {id_val[:8]}...")
        print(f"   Sender Session: {sender_sid[:8] if sender_sid else 'None'}...")
        print(f"   Receiver Session: {receiver_sid[:8] if receiver_sid else 'None'}...")
        print(f"   In Reply To: {in_reply_to[:8] if in_reply_to else 'None'}...")

        # 验证：所有回复邮件的receiver_session_id都应该正确
        if in_reply_to:
            # 查找被回复邮件的发送者
            cursor2 = conn.cursor()
            cursor2.execute('SELECT sender FROM emails WHERE id = ?', (in_reply_to,))
            result = cursor2.fetchone()
            if result:
                original_sender = result[0]
                # 验证：这封邮件的收件人应该恢复正确的session
                print(f"   🔍 回复给: {original_sender}")

                # 被回复邮件的sender_session_id
                cursor3 = conn.cursor()
                cursor3.execute('SELECT sender_session_id FROM emails WHERE id = ?', (in_reply_to,))
                result3 = cursor3.fetchone()

                if result3 and result3[0]:
                    original_sender_session = result3[0]

                    # 检查receiver_session_id是否正确
                    # 对于User->Agent的邮件，receiver_session_id应该是Agent的session
                    # 对于Agent->User的邮件，receiver_session_id应该是User的session

                    if recipient == 'Agent':
                        # 收件人是Agent，检查receiver_session_id是否为Agent的session
                        if receiver_sid == session1['session_id']:
                            print(f"   ✅ Receiver Session正确 (Agent的session)")
                        else:
                            print(f"   ❌ Receiver Session错误!")
                            print(f"      期望: {session1['session_id'][:8]}... (Agent)")
                            print(f"      实际: {receiver_sid[:8] if receiver_sid else 'None'}...")
                            return False
                    elif recipient == 'User':
                        # 收件人是User，检查receiver_session_id是否为User的session
                        if receiver_sid == user_session_id:
                            print(f"   ✅ Receiver Session正确 (User的session)")
                        else:
                            print(f"   ❌ Receiver Session错误!")
                            print(f"      期望: {user_session_id[:8]}... (User)")
                            print(f"      实际: {receiver_sid[:8] if receiver_sid else 'None'}...")
                            return False

    conn.close()

    # 验证Session目录
    print(f"\n📁 Session目录结构:")
    sessions_dir = test_world / '.matrix/sessions'
    if sessions_dir.exists():
        for agent_dir in sessions_dir.iterdir():
            if agent_dir.is_dir():
                print(f"   📂 Agent: {agent_dir.name}")
                for task_dir in agent_dir.iterdir():
                    if task_dir.is_dir():
                        print(f"     📄 Task: {task_dir.name[:8]}...")
                        history_dir = task_dir / 'history'
                        if history_dir.exists():
                            sessions = list(history_dir.iterdir())
                            print(f"       Sessions: {len([s for s in sessions if s.is_dir()])}")
                            for session_dir_item in sessions:
                                if session_dir_item.is_dir():
                                    history_file = session_dir_item / 'history.json'
                                    if history_file.exists():
                                        with open(history_file, 'r') as f:
                                            data = json.load(f)
                                            print(f"         {session_dir_item.name[:8]}... - {len(data.get('history', []))} messages ✅")
                                    else:
                                        print(f"         {session_dir_item.name[:8]}... - ❌ 缺少history.json")
                        else:
                            print(f"       ❌ 缺少history目录")

    # 清理
    if hasattr(db, 'conn') and db.conn:
        db.conn.close()

    shutil.rmtree(test_world)
    print(f"\n✅ 测试环境已清理")

    print(f"\n✅ 所有测试通过！Session管理完全正确！")
    return True


if __name__ == '__main__':
    try:
        success = asyncio.run(final_test())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
