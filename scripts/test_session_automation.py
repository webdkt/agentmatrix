#!/usr/bin/env python3
"""
Session管理自动化测试

完整测试流程：
1. 初始化测试环境
2. 创建测试Agent
3. 测试邮件发送和接收
4. 验证session目录结构
5. 验证数据库记录
"""

import sys
import os
import asyncio
import json
import shutil
import yaml
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agentmatrix.core.runtime import AgentMatrix
from agentmatrix.core.message import Email
from agentmatrix.core.paths import MatrixPaths


class SessionTester:
    def __init__(self):
        self.test_world_dir = Path('./TestSessionWorld')
        self.agent_configs = []
        self.emails_sent = []

    def setup_environment(self):
        """初始化测试环境"""
        print("=" * 70)
        print("步骤1: 初始化测试环境")
        print("=" * 70)

        # 清理旧环境
        if self.test_world_dir.exists():
            shutil.rmtree(self.test_world_dir)

        # 使用server.py的冷启动逻辑
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        import server
        server.create_directory_structure(self.test_world_dir, 'TestUser')
        server.create_world_config(self.test_world_dir, 'TestUser')

        # 创建mock LLM配置
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

        llm_config_path = self.test_world_dir / '.matrix/configs/agents/llm_config.json'
        llm_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(llm_config_path, 'w') as f:
            json.dump(llm_config, f, indent=2)

        print(f"✅ 测试环境已创建: {self.test_world_dir}")
        print(f"   Matrix Root: {self.test_world_dir}")

        # 验证目录结构
        paths = MatrixPaths(str(self.test_world_dir))
        print(f"\n✅ 目录结构验证:")
        print(f"   System Dir: {paths.system_dir}")
        print(f"   Configs Dir: {paths.config_dir}")
        print(f"   Sessions Dir: {paths.sessions_dir}")
        print(f"   Database Path: {paths.database_path}")

        return paths

    def create_test_agents(self):
        """创建测试Agent"""
        print("\n" + "=" * 70)
        print("步骤2: 创建测试Agent")
        print("=" * 70)

        # 创建User Agent
        user_agent_config = {
            'name': 'TestUser',
            'description': 'Test User Agent',
            'class_name': 'agentmatrix.agents.user_proxy.UserProxyAgent',
            'backend_model': 'default_llm',
            'mixins': ['skills.filesystem.FileSkillMixin'],
            'attribute_initializations': {'on_mail_received': None}
        }

        user_yml = self.test_world_dir / '.matrix/configs/agents/TestUser.yml'
        with open(user_yml, 'w', encoding='utf-8') as f:
            yaml.dump(user_agent_config, f, allow_unicode=True)

        print(f"✅ 创建User Agent: {user_agent_config['name']}")

        # 创建Test Agent
        test_agent_config = {
            'name': 'TestAgent',
            'description': 'Test Agent for session management',
            'class_name': 'agentmatrix.agents.base.BaseAgent',
            'backend_model': 'default_llm',
            'skills': ['memory'],
            'persona': {
                'base': '你是一个测试Agent。'
            }
        }

        test_yml = self.test_world_dir / '.matrix/configs/agents/TestAgent.yml'
        with open(test_yml, 'w', encoding='utf-8') as f:
            yaml.dump(test_agent_config, f, allow_unicode=True)

        print(f"✅ 创建Test Agent: {test_agent_config['name']}")

        self.agent_configs = [user_agent_config, test_agent_config]
        return user_agent_config, test_agent_config

    def verify_session_structure(self):
        """验证session目录结构"""
        print("\n" + "=" * 70)
        print("步骤3: 验证Session目录结构")
        print("=" * 70)

        paths = MatrixPaths(str(self.test_world_dir))
        sessions_dir = paths.sessions_dir

        print(f"Sessions目录: {sessions_dir}")

        if not sessions_dir.exists():
            print("❌ Sessions目录不存在")
            return False

        # 检查Agent子目录
        agent_dirs = list(sessions_dir.iterdir())
        print(f"\n找到 {len(agent_dirs)} 个Agent目录:")

        for agent_dir in agent_dirs:
            if agent_dir.is_dir():
                print(f"\n  📁 Agent: {agent_dir.name}")
                task_dirs = list(agent_dir.iterdir())
                for task_dir in task_dirs:
                    if task_dir.is_dir():
                        print(f"    📂 Task: {task_dir.name}")
                        history_dir = task_dir / "history"
                        if history_dir.exists():
                            print(f"      📄 history/ 目录存在 ✅")
                            session_dirs = list(history_dir.iterdir())
                            print(f"        Sessions: {len([d for d in session_dirs if d.is_dir()])}")
                        else:
                            print(f"      ❌ history/ 目录不存在")

        return True

    async def test_email_workflow(self):
        """测试完整的邮件工作流"""
        print("\n" + "=" * 70)
        print("步骤4: 测试邮件工作流")
        print("=" * 70)

        try:
            # 注意：这里我们不真正启动runtime，因为需要Docker
            # 我们只测试session管理的逻辑

            from agentmatrix.core.session_manager import SessionManager

            # 创建SessionManager
            session_mgr = SessionManager(
                agent_name='TestAgent',
                matrix_path=str(self.test_world_dir)
            )

            print("✅ SessionManager已创建")

            # 模拟邮件1：TestUser -> TestAgent
            task_id = str(uuid4())
            email1 = Email(
                sender='TestUser',
                recipient='TestAgent',
                subject='Test Email 1',
                body='This is test email 1',
                task_id=task_id,
                sender_session_id=str(uuid4()),
                receiver_session_id=None  # 第一次接收，为None
            )

            print(f"\n📧 邮件1: {email1.sender} -> {email1.recipient}")
            print(f"   Subject: {email1.subject}")
            print(f"   Task ID: {email1.task_id}")
            print(f"   Receiver Session ID: {email1.receiver_session_id} (第一次接收)")

            # 获取session（这会创建新的session）
            session1 = await session_mgr.get_session(email1)
            print(f"   ✅ Session已创建: {session1['session_id'][:8]}...")

            # 先插入邮件到数据库
            from agentmatrix.db.agent_matrix_db import AgentMatrixDB
            db = AgentMatrixDB(str(session_mgr.matrixpath.database_path))
            db.log_email(email1)
            print(f"   ✅ 邮件已插入数据库")
            
            # 然后更新receiver_session_id
            db.update_receiver_session(
                email1.id,
                session1['session_id'],
                'TestAgent'
            )
            print(f"   ✅ Receiver Session ID已更新")
            
            if hasattr(db, 'conn') and db.conn:
                db.conn.close()
            print(f"   ✅ Receiver Session ID已更新")

            # 验证session目录
            paths = MatrixPaths(str(self.test_world_dir))
            session_dir = paths.get_agent_session_history_dir('TestAgent', task_id, session1['session_id'])
            print(f"   📁 Session目录: {session_dir}")

            history_file = session_dir / 'history.json'
            context_file = session_dir / 'context.json'

            print(f"   📄 history.json: {'✅ 存在' if history_file.exists() else '❌ 不存在'}")
            print(f"   📄 context.json: {'✅ 存在' if context_file.exists() else '❌ 不存在'}")

            # 模拟邮件2：TestAgent -> TestUser (回复邮件1)
            email2 = Email(
                sender='TestAgent',
                recipient='TestUser',
                subject='Re: Test Email 1',
                body='This is reply to email 1',
                in_reply_to=email1.id,
                task_id=task_id,
                sender_session_id=session1['session_id'],
                receiver_session_id=email1.sender_session_id
            )

            print(f"\n📧 邮件2: {email2.sender} -> {email2.recipient}")
            print(f"   Subject: {email2.subject}")
            print(f"   In Reply To: {email2.in_reply_to}")
            print(f"   Sender Session ID: {email2.sender_session_id[:8]}...")
            print(f"   Receiver Session ID: {email2.receiver_session_id[:8]}...")

            # 记录邮件
            self.emails_sent = [email1, email2]

            return True

        except Exception as e:
            print(f"❌ 测试邮件工作流失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def verify_database_records(self):
        """验证数据库记录"""
        print("\n" + "=" * 70)
        print("步骤5: 验证数据库记录")
        print("=" * 70)

        try:
            import sqlite3
            from agentmatrix.db.agent_matrix_db import AgentMatrixDB

            paths = MatrixPaths(str(self.test_world_dir))
            db_path = paths.database_path

            if not db_path.exists():
                print(f"❌ 数据库不存在: {db_path}")
                return False

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 查询所有邮件
            cursor.execute('SELECT * FROM emails ORDER BY timestamp')
            emails = cursor.fetchall()

            cursor.execute('PRAGMA table_info(emails)')
            columns = [col[1] for col in cursor.fetchall()]

            print(f"找到 {len(emails)} 封邮件:")

            for i, email in enumerate(emails, 1):
                print(f"\n📧 邮件 {i}:")
                email_dict = dict(zip(columns, email))
                print(f"   ID: {email_dict['id'][:8]}...")
                print(f"   From: {email_dict['sender']}")
                print(f"   To: {email_dict['recipient']}")
                print(f"   Subject: {email_dict['subject']}")
                print(f"   Task ID: {email_dict['task_id'][:8]}...")
                print(f"   Sender Session: {email_dict.get('sender_session_id', 'None')[:8] if email_dict.get('sender_session_id') else 'None'}...")
                print(f"   Receiver Session: {email_dict.get('receiver_session_id', 'None')[:8] if email_dict.get('receiver_session_id') else 'None'}...")
                print(f"   In Reply To: {email_dict.get('in_reply_to', 'None')[:8] if email_dict.get('in_reply_to') else 'None'}...")

            conn.close()
            return True

        except Exception as e:
            print(f"❌ 验证数据库记录失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def verify_reply_chain(self):
        """验证回复链的正确性"""
        print("\n" + "=" * 70)
        print("步骤6: 验证回复链")
        print("=" * 70)

        try:
            import sqlite3
            paths = MatrixPaths(str(self.test_world_dir))
            conn = sqlite3.connect(paths.database_path)
            cursor = conn.cursor()

            # 查询邮件，找到回复关系
            cursor.execute('''
                SELECT
                    id, sender, recipient, subject,
                    sender_session_id, receiver_session_id,
                    in_reply_to, task_id
                FROM emails
                ORDER BY timestamp
            ''')

            emails = cursor.fetchall()

            print("回复链分析:")
            for email in emails:
                id_val, sender, recipient, subject, sender_sid, receiver_sid, in_reply_to, task_id = email

                print(f"\n📧 {subject}")
                print(f"   From: {sender} (session: {sender_sid[:8] if sender_sid else 'None'}...)")
                print(f"   To: {recipient} (session: {receiver_sid[:8] if receiver_sid else 'None'}...)")

                if in_reply_to:
                    print(f"   💬 回复邮件: {in_reply_to[:8]}...")

                    # 查找被回复的邮件
                    cursor.execute('SELECT sender_session_id FROM emails WHERE id = ?', (in_reply_to,))
                    result = cursor.fetchone()
                    if result:
                        original_sender_sid = result[0]
                        if receiver_sid == original_sender_sid:
                            print(f"   ✅ Receiver Session正确: {receiver_sid[:8]}... == {original_sender_sid[:8]}...")
                        else:
                            print(f"   ❌ Receiver Session错误: {receiver_sid[:8]}... != {original_sender_sid[:8]}...")
                            print(f"      期望: {original_sender_sid}")
                            print(f"      实际: {receiver_sid}")
                            return False

            conn.close()
            return True

        except Exception as e:
            print(f"❌ 验证回复链失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def cleanup(self):
        """清理测试环境"""
        print("\n" + "=" * 70)
        print("清理测试环境")
        print("=" * 70)

        if self.test_world_dir.exists():
            shutil.rmtree(self.test_world_dir)
            print(f"✅ 已删除测试环境: {self.test_world_dir}")

    async def run_all_tests(self):
        """运行所有测试"""
        try:
            # 步骤1: 初始化环境
            paths = self.setup_environment()

            # 步骤2: 创建Agent
            self.create_test_agents()

            # 步骤3: 验证目录结构
            if not self.verify_session_structure():
                print("❌ 目录结构验证失败")
                return False

            # 步骤4: 测试邮件工作流
            if not await self.test_email_workflow():
                print("❌ 邮件工作流测试失败")
                return False

            # 步骤5: 验证数据库记录
            if not self.verify_database_records():
                print("❌ 数据库记录验证失败")
                return False

            # 步骤6: 验证回复链
            if not self.verify_reply_chain():
                print("❌ 回复链验证失败")
                return False

            print("\n" + "=" * 70)
            print("✅ 所有测试通过！")
            print("=" * 70)
            return True

        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            # 清理
            self.cleanup()


async def main():
    """主函数"""
    tester = SessionTester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    asyncio.run(main())
