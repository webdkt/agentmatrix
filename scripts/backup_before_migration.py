#!/usr/bin/env python3
"""
Backup Script - 备份脚本

在迁移前创建完整备份
"""

import os
import shutil
import sys
from pathlib import Path
from datetime import datetime


def create_backup(matrix_root: str) -> str:
    """
    创建备份

    Args:
        matrix_root: Matrix World根目录

    Returns:
        备份目录路径
    """
    matrix_root = Path(matrix_root).resolve()

    # 创建备份目录
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir = matrix_root.parent / backup_name

    print(f"📦 创建备份: {backup_dir}")

    # 复制整个目录
    shutil.copytree(matrix_root, backup_dir)

    print(f"✅ 备份完成: {backup_dir}")
    return str(backup_dir)


def verify_backup(backup_dir: str) -> bool:
    """
    验证备份是否完整

    Args:
        backup_dir: 备份目录路径

    Returns:
        True如果备份完整，否则False
    """
    backup_path = Path(backup_dir)

    # 检查必需的文件和目录
    required_items = [
        ".matrix",
        "agents",
        "workspace",
    ]

    for item in required_items:
        item_path = backup_path / item
        if not item_path.exists():
            print(f"❌ 备份验证失败: 缺少 {item}")
            return False

    print("✅ 备份验证成功")
    return True


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法: python backup_before_migration.py <matrix_root>")
        print("示例: python backup_before_migration.py ./MyWorld")
        sys.exit(1)

    matrix_root = sys.argv[1]

    if not os.path.exists(matrix_root):
        print(f"❌ 错误: 目录不存在: {matrix_root}")
        sys.exit(1)

    try:
        # 创建备份
        backup_dir = create_backup(matrix_root)

        # 验证备份
        if verify_backup(backup_dir):
            print(f"\n🎉 备份成功！可以安全地进行迁移。")
            print(f"备份位置: {backup_dir}")
        else:
            print(f"\n❌ 备份验证失败，请检查备份目录: {backup_dir}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ 备份失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
