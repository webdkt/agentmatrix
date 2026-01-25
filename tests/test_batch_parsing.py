#!/usr/bin/env python
"""
测试 _parse_batch_output 的推荐链接解析功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# 需要创建一个最小的 WebSearcherMixin 实例来测试
from agentmatrix.skills.web_searcher import WebSearcherMixin

class MinimalWebSearcher(WebSearcherMixin):
    def __init__(self):
        self.logger = type('Logger', (), {
            'debug': lambda msg: None,
            'info': lambda msg: None,
            'warning': lambda msg: None,
            'error': lambda msg: None
        })()

def test_parse_batch_output():
    """测试批处理输出的解析"""

    searcher = MinimalWebSearcher()

    # 测试用例
    test_cases = [
        {
            "name": "基本笔记（无链接）",
            "input": """##值得记录的笔记
这是有用的信息。
来源：https://example.com""",
            "expected_heading": "note",
            "expected_links": []
        },
        {
            "name": "笔记（带推荐链接）",
            "input": """##值得记录的笔记
这是有用的信息。
来源：https://example.com

====推荐链接====
2024财报
下载(2)
====推荐链接结束====""",
            "expected_heading": "note",
            "expected_links": ["2024财报", "下载(2)"]
        },
        {
            "name": "找到答案（带链接）",
            "input": """##对问题的回答
根据文档，答案是42。

====推荐链接====
相关文档
====推荐链接结束====""",
            "expected_heading": "answer",
            "expected_links": ["相关文档"]
        },
        {
            "name": "继续阅读（无链接）",
            "input": """##没有值得记录的笔记继续阅读
这段内容不相关。""",
            "expected_heading": "continue",
            "expected_links": []
        },
        {
            "name": "放弃文档",
            "input": """##完全不相关的文档应该放弃
这是广告内容。""",
            "expected_heading": "skip_doc",
            "expected_links": []
        }
    ]

    print("=== 测试 _parse_batch_output ===\n")

    for i, test in enumerate(test_cases, 1):
        print(f"测试 {i}: {test['name']}")
        result = searcher._parse_batch_output(test["input"])

        # 检查状态
        if result["status"] != "success":
            print(f"  ❌ 解析失败: status={result['status']}")
            continue

        # 检查标题类型
        if result["heading_type"] != test["expected_heading"]:
            print(f"  ❌ 标题类型不匹配: 期望 {test['expected_heading']}, 实际 {result['heading_type']}")
            continue

        # 检查链接
        if result["found_links"] != test["expected_links"]:
            print(f"  ❌ 链接不匹配:")
            print(f"     期望: {test['expected_links']}")
            print(f"     实际: {result['found_links']}")
            continue

        print(f"  ✅ 通过")

    print("\n✅ 所有测试完成!")

if __name__ == "__main__":
    test_parse_batch_output()
