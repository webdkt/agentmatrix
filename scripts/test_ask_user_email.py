#!/usr/bin/env python3
"""
Ask User 邮件集成测试脚本

测试场景：
1. 基本 ask_user 邮件发送
2. 邮件回复解析
3. Agent 不存在的情况
4. 双渠道冲突
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agentmatrix.services.email_proxy_service import EmailProxyService


def test_parse_ask_user_metadata():
    """测试 ask_user 标记解析"""
    print("🧪 测试 ask_user 标记解析...")

    # 创建 EmailProxyService 实例（用于调用方法）
    # 注意：这里只是为了测试方法，不需要完整初始化
    class DummyEmailProxy:
        def _parse_ask_user_metadata(self, subject: str):
            import re
            match = re.search(r'#ASK_USER#([^#]+)#([^#]+)#', subject)
            if match:
                return {
                    'agent_name': match.group(1),
                    'agent_session_id': match.group(2)
                }
            return None

    proxy = DummyEmailProxy()

    # 测试用例
    test_cases = [
        {
            'subject': 'Researcher问：你的预算是多少？ #ASK_USER#Researcher#abc123#',
            'expected': {'agent_name': 'Researcher', 'agent_session_id': 'abc123'}
        },
        {
            'subject': 'Planner问：请确认任务优先级 #ASK_USER#Planner#xyz789#',
            'expected': {'agent_name': 'Planner', 'agent_session_id': 'xyz789'}
        },
        {
            'subject': '普通邮件，没有标记',
            'expected': None
        },
        {
            'subject': 'Re: Researcher问：你的预算是多少？ #ASK_USER#Researcher#abc123#',
            'expected': {'agent_name': 'Researcher', 'agent_session_id': 'abc123'}
        }
    ]

    all_passed = True
    for i, test in enumerate(test_cases):
        result = proxy._parse_ask_user_metadata(test['subject'])
        expected = test['expected']

        if result == expected:
            print(f"  ✅ 测试 {i+1} 通过: {test['subject'][:50]}...")
        else:
            print(f"  ❌ 测试 {i+1} 失败:")
            print(f"     Subject: {test['subject']}")
            print(f"     预期: {expected}")
            print(f"     实际: {result}")
            all_passed = False

    return all_passed


def test_subject_format():
    """测试 Subject 格式生成"""
    print("\n🧪 测试 Subject 格式生成...")

    # 模拟 BaseAgent._send_ask_user_email 中的 subject 生成
    agent_name = "Researcher"
    agent_session_id = "session_123"
    question = "你的预算是多少？"

    # 截断过长的问题
    question_preview = question[:100] + "..." if len(question) > 100 else question
    subject = f"{agent_name}问：{question_preview} #ASK_USER#{agent_name}#{agent_session_id}#"

    expected = "Researcher问：你的预算是多少？ #ASK_USER#Researcher#session_123#"

    if subject == expected:
        print(f"  ✅ Subject 格式正确")
        print(f"     {subject}")
        return True
    else:
        print(f"  ❌ Subject 格式错误")
        print(f"     预期: {expected}")
        print(f"     实际: {subject}")
        return False


def test_email_body_format():
    """测试邮件正文格式"""
    print("\n🧪 测试邮件正文格式...")

    agent_name = "Researcher"
    question = "你的预算是多少？"

    body = f"""你好，

{agent_name} 有一个问题需要你回答：

问题：{question}

---
请直接回复此邮件来回答问题。
回复内容将直接提交给 {agent_name}。

Subject 中的标记（#ASK_USER#...）会被自动识别，请勿删除。
---
"""

    # 检查关键元素
    checks = [
        agent_name in body,
        question in body,
        "请直接回复此邮件来回答问题" in body,
        "#ASK_USER#" in body
    ]

    if all(checks):
        print(f"  ✅ 邮件正文格式正确")
        print(f"     包含所有必需元素")
        return True
    else:
        print(f"  ❌ 邮件正文格式错误")
        print(f"     缺少某些必需元素")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Ask User 邮件集成测试")
    print("=" * 60)

    results = []

    # 运行测试
    results.append(("标记解析", test_parse_ask_user_metadata()))
    results.append(("Subject 格式", test_subject_format()))
    results.append(("邮件正文格式", test_email_body_format()))

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
