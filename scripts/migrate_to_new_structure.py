#!/usr/bin/env python3
"""
Migration Script - 迁移脚本

将旧的目录结构迁移到新的目录结构
"""

import os
import shutil
import sys
import json
import yaml
from pathlib import Path
from datetime import datetime


def migrate_agents_to_config(matrix_root: Path, dry_run: bool = False):
    """
    迁移agents目录到.matrix/configs/agents/

    Args:
        matrix_root: Matrix根目录
        dry_run: 是否为试运行
    """
    old_agents_dir = matrix_root / "agents"
    new_agents_dir = matrix_root / ".matrix" / "configs" / "agents"

    if not old_agents_dir.exists():
        print("⚠️  旧的agents目录不存在，跳过")
        return

    print(f"📁 迁移agents配置:")
    print(f"  旧: {old_agents_dir}")
    print(f"  新: {new_agents_dir}")

    if not dry_run:
        # 创建新目录
        new_agents_dir.mkdir(parents=True, exist_ok=True)

        # 复制所有yml文件和llm_config.json
        for file in old_agents_dir.iterdir():
            if file.suffix in ['.yml', '.yaml'] or file.name == 'llm_config.json':
                dest = new_agents_dir / file.name
                shutil.copy2(file, dest)
                print(f"  ✅ 复制: {file.name}")


def migrate_system_config(matrix_root: Path, dry_run: bool = False):
    """
    迁移system_config.yml到.matrix/configs/

    Args:
        matrix_root: Matrix根目录
        dry_run: 是否为试运行
    """
    old_config = matrix_root / "system_config.yml"
    new_config = matrix_root / ".matrix" / "configs" / "system_config.yml"

    if not old_config.exists():
        print("⚠️  system_config.yml不存在，跳过")
        return

    print(f"📄 迁移系统配置:")
    print(f"  旧: {old_config}")
    print(f"  新: {new_config}")

    if not dry_run:
        # 创建新目录
        new_config.parent.mkdir(parents=True, exist_ok=True)

        # 复制配置文件
        shutil.copy2(old_config, new_config)
        print(f"  ✅ 复制: system_config.yml")


def migrate_database(matrix_root: Path, dry_run: bool = False):
    """
    迁移数据库到.matrix/database/

    Args:
        matrix_root: Matrix根目录
        dry_run: 是否为试运行
    """
    old_db = matrix_root / ".matrix" / "agentmatrix.db"
    new_db = matrix_root / ".matrix" / "database" / "agentmatrix.db"

    if not old_db.exists():
        print("⚠️  数据库不存在，跳过")
        return

    print(f"💾 迁移数据库:")
    print(f"  旧: {old_db}")
    print(f"  新: {new_db}")

    if not dry_run:
        # 创建新目录
        new_db.parent.mkdir(parents=True, exist_ok=True)

        # 移动数据库文件
        shutil.move(str(old_db), str(new_db))
        print(f"  ✅ 移动: agentmatrix.db")


def migrate_sessions(matrix_root: Path, dry_run: bool = False):
    """
    迁移sessions到新的目录结构

    旧结构: workspace/.matrix/{agent_name}/{task_id}/history/
    新结构: .matrix/sessions/{agent_name}/{task_id}/history/

    Args:
        matrix_root: Matrix根目录
        dry_run: 是否为试运行
    """
    old_sessions_base = matrix_root / "workspace" / ".matrix"
    new_sessions_base = matrix_root / ".matrix" / "sessions"

    if not old_sessions_base.exists():
        print("⚠️  旧sessions目录不存在，跳过")
        return

    print(f"📂 迁移sessions:")
    print(f"  旧: {old_sessions_base}")
    print(f"  新: {new_sessions_base}")

    if not dry_run:
        # 创建新目录
        new_sessions_base.mkdir(parents=True, exist_ok=True)

        # 移动所有agent的sessions
        for agent_dir in old_sessions_base.iterdir():
            if agent_dir.is_dir():
                new_agent_dir = new_sessions_base / agent_dir.name
                shutil.move(str(agent_dir), str(new_agent_dir))
                print(f"  ✅ 移动: {agent_dir.name}")


def migrate_workspace(matrix_root: Path, dry_run: bool = False):
    """
    迁移workspace内容

    确保workspace目录结构正确

    Args:
        matrix_root: Matrix根目录
        dry_run: 是否为试运行
    """
    workspace_dir = matrix_root / "workspace"
    agent_files_dir = workspace_dir / "agent_files"
    skills_dir = workspace_dir / "SKILLS"

    print(f"🏭 迁移workspace:")

    if not dry_run:
        # 创建workspace目录结构
        workspace_dir.mkdir(parents=True, exist_ok=True)
        agent_files_dir.mkdir(parents=True, exist_ok=True)
        skills_dir.mkdir(parents=True, exist_ok=True)

        print(f"  ✅ 创建workspace目录结构")


def create_default_matrix_config(matrix_root: Path, dry_run: bool = False):
    """
    创建默认的matrix_config.yml

    Args:
        matrix_root: Matrix根目录
        dry_run: 是否为试运行
    """
    matrix_config_path = matrix_root / ".matrix" / "configs" / "matrix_config.yml"

    if matrix_config_path.exists():
        print("⚠️  matrix_config.yml已存在，跳过")
        return

    print(f"📝 创建默认Matrix配置:")

    default_config = {
        'user_agent_name': 'User',
        'matrix_version': '1.0.0',
        'description': 'AgentMatrix World',
        'timezone': 'UTC'
    }

    if not dry_run:
        # 创建配置文件
        matrix_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(matrix_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
        print(f"  ✅ 创建: matrix_config.yml")


def verify_migration(matrix_root: Path) -> bool:
    """
    验证迁移是否成功

    Args:
        matrix_root: Matrix根目录

    Returns:
        True如果迁移成功，否则False
    """
    required_items = [
        ".matrix/configs/agents",
        ".matrix/configs/system_config.yml",
        ".matrix/configs/matrix_config.yml",
        ".matrix/database",
        ".matrix/logs",
        ".matrix/sessions",
        "workspace/agent_files",
        "workspace/SKILLS",
    ]

    print("🔍 验证迁移结果:")

    all_ok = True
    for item in required_items:
        item_path = matrix_root / item
        if item_path.exists():
            print(f"  ✅ {item}")
        else:
            print(f"  ❌ {item} (缺失)")
            all_ok = False

    return all_ok


def migrate(matrix_root: str, dry_run: bool = False):
    """
    执行完整迁移

    Args:
        matrix_root: Matrix根目录
        dry_run: 是否为试运行
    """
    matrix_root = Path(matrix_root).resolve()

    print(f"\n{'='*60}")
    print(f"🚀 开始迁移: {matrix_root}")
    if dry_run:
        print(f"⚠️  试运行模式 - 不会实际修改文件")
    print(f"{'='*60}\n")

    # 执行迁移步骤
    migrate_agents_to_config(matrix_root, dry_run)
    print()

    migrate_system_config(matrix_root, dry_run)
    print()

    migrate_database(matrix_root, dry_run)
    print()

    migrate_sessions(matrix_root, dry_run)
    print()

    migrate_workspace(matrix_root, dry_run)
    print()

    create_default_matrix_config(matrix_root, dry_run)
    print()

    # 验证迁移
    if not dry_run:
        if verify_migration(matrix_root):
            print(f"\n{'='*60}")
            print(f"🎉 迁移成功！")
            print(f"{'='*60}\n")
        else:
            print(f"\n{'='*60}")
            print(f"❌ 迁移验证失败，请检查")
            print(f"{'='*60}\n")
    else:
        print(f"\n{'='*60}")
        print(f"🔍 试运行完成")
        print(f"{'='*60}\n")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法: python migrate_to_new_structure.py <matrix_root> [--dry-run]")
        print("示例: python migrate_to_new_structure.py ./MyWorld")
        print("      python migrate_to_new_structure.py ./MyWorld --dry-run")
        sys.exit(1)

    matrix_root = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if not os.path.exists(matrix_root):
        print(f"❌ 错误: 目录不存在: {matrix_root}")
        sys.exit(1)

    try:
        # 提示用户备份
        if not dry_run:
            print("⚠️  警告: 此操作将修改目录结构")
            print("💡 建议: 在迁移前先运行备份脚本: python backup_before_migration.py")
            response = input("是否继续? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ 取消迁移")
                sys.exit(0)

        # 执行迁移
        migrate(matrix_root, dry_run)

    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
