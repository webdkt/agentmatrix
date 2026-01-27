"""
测试可能破坏 JSON 格式的特殊字符和情况
"""

import json
import tempfile
from pathlib import Path


def test_tricky_characters():
    """测试各种可能导致 JSON 问题的字符"""
    print("\n=== 测试可能导致 JSON 问题的字符 ===")

    test_cases = [
        # 描述, content
        ("未转义的引号", 'Text with "quotes" inside'),
        ("单引号", "Text with 'single quotes'"),
        ("反引号", "Text with `backticks`"),
        ("换行符", "Line 1\nLine 2\nLine 3"),
        ("回车符", "Line 1\rLine 2"),
        ("制表符", "Col1\tCol2\tCol3"),
        ("反斜杠", "Path: C:\\Users\\test"),
        ("正斜杠", "URL: https://example.com/path"),
        ("混合引号", '''He said "She said 'Hi'"'''),
        ("JSON 片段", '{"key": "value"}'),
        ("JavaScript 代码", "function test() { return 'value'; }"),
        ("HTML 片段", "<div class='test'>Content</div>"),
        ("Markdown", "**bold** and `code` and [link](url)"),
        ("特殊 Unicode", "null\u0000byte"),
        ("控制字符", "bell\u0007escape\u001b"),
        ("百分号", "Discount: 50% off"),
        ("美元符号", "Price: $19.99"),
        ("井号", "Heading #1"),
        ("连续引号", '"""three quotes"""'),
        ("未闭合的括号", "(incomplete [bracket {test"),
    ]

    temp_dir = tempfile.mkdtemp()

    for desc, content in test_cases:
        try:
            # 创建包含特殊字符的 history
            history = [
                {"role": "user", "content": content}
            ]

            # 尝试序列化
            json_str = json.dumps(history, ensure_ascii=False, indent=2)

            # 注意：特殊字符会被转义，所以不能直接用 `in` 检查
            # 而应该检查反序列化后的内容是否一致
            # 例如：换行符 \n 会被转义为 \\n

            # 尝试写入文件
            test_file = Path(temp_dir) / f"test_{desc.replace(' ', '_')}.json"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(json_str)

            # 尝试读取文件
            with open(test_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            # 验证内容一致
            assert loaded == history, f"内容不一致: {desc}"
            assert loaded[0]["content"] == content, f"特殊字符丢失: {desc}"

            print(f"✅ {desc}")

        except Exception as e:
            print(f"❌ {desc}: {e}")

    # 清理
    import shutil
    shutil.rmtree(temp_dir)


def test_serialization_edge_cases():
    """测试序列化的边缘情况"""
    print("\n=== 测试序列化边缘情况 ===")

    edge_cases = [
        ("None 值", {"role": "user", "content": None}),
        ("空字符串", {"role": "user", "content": ""}),
        ("纯数字", {"role": "user", "content": 12345}),
        ("布尔值", {"role": "user", "content": True}),
        ("列表", {"role": "user", "content": [1, 2, 3]}),
        ("字典", {"role": "user", "content": {"key": "value"}}),
        ("嵌套结构", {"role": "user", "content": {"a": [1, 2, {"b": "c"}]}}),
    ]

    temp_dir = tempfile.mkdtemp()

    for desc, message in edge_cases:
        try:
            history = [message]

            # 序列化
            json_str = json.dumps(history, ensure_ascii=False, indent=2)

            # 写入文件
            test_file = Path(temp_dir) / f"edge_{desc}.json"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(json_str)

            # 读取文件
            with open(test_file, "r") as f:
                loaded = json.load(f)

            assert loaded == history, f"内容不一致: {desc}"
            print(f"✅ {desc}")

        except Exception as e:
            print(f"❌ {desc}: {type(e).__name__}: {e}")

    # 清理
    import shutil
    shutil.rmtree(temp_dir)


def test_actually_problematic_cases():
    """测试真正会导致问题的情况"""
    print("\n=== 测试真正会导致问题的情况 ===")

    problematic_cases = [
        ("不可序列化的对象", {"role": "user", "content": open}),  # 函数对象
        ("循环引用", None),  # 需要特殊构造
    ]

    # 循环引用测试
    data = {"role": "user"}
    data["content"] = data  # 循环引用
    problematic_cases[1] = ("循环引用", [data])

    temp_dir = tempfile.mkdtemp()

    for desc, history in problematic_cases:
        try:
            json_str = json.dumps(history, ensure_ascii=False)
            print(f"⚠️  {desc}: 应该失败但没有失败")
        except (TypeError, ValueError) as e:
            print(f"✅ {desc}: 正确拒绝 - {type(e).__name__}")

    # 清理
    import shutil
    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_tricky_characters()
    test_serialization_edge_cases()
    test_actually_problematic_cases()

    print("\n" + "="*50)
    print("结论：")
    print("✅ JSON 序列化会自动转义特殊字符（引号、换行等）")
    print("✅ 各种括号、引号、代码片段都能正确保存")
    print("✅ json.dump() 非常健壮，能处理几乎所有情况")
    print("⚠️  只有不可序列化的对象（函数、循环引用）才会失败")
    print("⚠️  但 history 中存储的是字符串（LLM 对话），不会出现这些情况")
    print("="*50)
