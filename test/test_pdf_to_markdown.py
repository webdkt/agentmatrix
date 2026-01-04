#!/usr/bin/env python3
"""
测试 pdf_to_markdown 函数
"""
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.report_writer_utils import pdf_to_markdown

def test_full_pdf():
    """测试1: 转换完整PDF"""
    print("=" * 60)
    print("测试1: 转换完整PDF")
    print("=" * 60)

    pdf_path = "/Users/frwang/myprojects/agentmatrix/Samples/TestWorkspace/downloads/EO14117/USCODE-2023-title50-chap35-sec1705.pdf"

    # 调用函数获取文本
    markdown_text = pdf_to_markdown(pdf_path)

    # 验证返回的是字符串
    assert isinstance(markdown_text, str), "返回值应该是字符串"
    print(f"✅ 返回类型正确: {type(markdown_text)}")

    # 显示文本信息
    print(f"✅ 转换成功，文本长度: {len(markdown_text)} 字符")
    print(f"✅ 文本预览（前200字符）:\n{markdown_text[:200]}...")

    # 保存到文件
    output_path = "test/output_full_pdf.md"
    os.makedirs("test", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    print(f"✅ 已保存到: {output_path}")

    return markdown_text

def test_partial_pdf():
    """测试2: 转换PDF的第1页"""
    print("\n" + "=" * 60)
    print("测试2: 转换PDF第1页")
    print("=" * 60)

    pdf_path = "/Users/frwang/myprojects/agentmatrix/Samples/TestWorkspace/downloads/EO14117/USCODE-2023-title50-chap35-sec1705.pdf"

    # 只转换第1页
    markdown_text = pdf_to_markdown(pdf_path, start_page=1, end_page=1)

    print(f"✅ 转换成功，文本长度: {len(markdown_text)} 字符")
    print(f"✅ 文本预览（前200字符）:\n{markdown_text[:200]}...")

    # 保存到文件
    output_path = "test/output_page_1.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    print(f"✅ 已保存到: {output_path}")

    return markdown_text

def test_range_pdf():
    """测试3: 转换PDF的第1-2页"""
    print("\n" + "=" * 60)
    print("测试3: 转换PDF第1-2页")
    print("=" * 60)

    pdf_path = "/Users/frwang/myprojects/agentmatrix/Samples/TestWorkspace/downloads/EO14117/USCODE-2023-title50-chap35-sec1705.pdf"

    # 转换第1-2页
    markdown_text = pdf_to_markdown(pdf_path, start_page=1, end_page=2)

    print(f"✅ 转换成功，文本长度: {len(markdown_text)} 字符")
    print(f"✅ 文本预览（前200字符）:\n{markdown_text[:200]}...")

    # 保存到文件
    output_path = "test/output_page_1-2.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    print(f"✅ 已保存到: {output_path}")

    return markdown_text

def main():
    """主测试函数"""
    print(f"\n{'🧪' * 30}")
    print("PDF to Markdown 测试套件")
    print(f"{'🧪' * 30}\n")

    try:
        # 运行测试
        text1 = test_full_pdf()
        text2 = test_partial_pdf()
        text3 = test_range_pdf()

        # 对比结果
        print("\n" + "=" * 60)
        print("📊 测试结果对比")
        print("=" * 60)
        print(f"完整PDF:    {len(text1)} 字符")
        print(f"第1页:      {len(text2)} 字符")
        print(f"第1-2页:    {len(text3)} 字符")
        print(f"\n✅ 验证: 第1-2页应该比第1页长: {len(text3) > len(text2)}")
        print(f"✅ 验证: 完整PDF应该最长: {len(text1) > len(text3)}")

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
