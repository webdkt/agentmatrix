#!/usr/bin/env python3
"""
统一存储路径迁移脚本

迁移内容：
1. Session history: .matrix/sessions/ → .matrix/{agent_name}/{user_session_id}/history/
2. Session memory db: .matrix/{agent_name}/memory/{user_session_id}/ → .matrix/{agent_name}/{user_session_id}/memory/
"""

import shutil
from pathlib import Path


def migrate_session_history(matrix_path: str, workspace_root: str, dry_run: bool = False):
    """
    迁移 session history 文件

    旧路径：{matrix_path}/.matrix/sessions/{user_session_id}/history/{agent_name}/{session_id}/
    新路径：{workspace_root}/.matrix/{agent_name}/{user_session_id}/history/{session_id}/
    """
    old_base = Path(matrix_path) / ".matrix" / "sessions"

    if not old_base.exists():
        print(f"旧 session history 路径不存在: {old_base}")
        return 0

    count = 0

    for user_session_dir in old_base.iterdir():
        if not user_session_dir.is_dir():
            continue

        user_session_id = user_session_dir.name
        history_dir = user_session_dir / "history"

        if not history_dir.exists():
            continue

        for agent_dir in history_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            agent_name = agent_dir.name

            # 迁移 session 目录
            for session_dir in agent_dir.iterdir():
                if not session_dir.is_dir():
                    continue

                session_id = session_dir.name
                new_session_dir = (
                    Path(workspace_root) / ".matrix" / agent_name /
                    user_session_id / "history" / session_id
                )

                print(f"迁移 history: {agent_name}/{user_session_id}/{session_id[:8]}")

                if dry_run:
                    print(f"  [DRY RUN] {session_dir} → {new_session_dir}")
                    count += 1
                    continue

                new_session_dir.mkdir(parents=True, exist_ok=True)

                # 复制文件
                for filename in ["history.json", "context.json"]:
                    src_file = session_dir / filename
                    if src_file.exists():
                        dst_file = new_session_dir / filename
                        shutil.copy2(src_file, dst_file)
                count += 1

            # 迁移 reply_mapping.json
            old_reply_mapping = agent_dir / "reply_mapping.json"
            if old_reply_mapping.exists():
                new_reply_mapping = (
                    Path(workspace_root) / ".matrix" / agent_name /
                    user_session_id / "history" / "reply_mapping.json"
                )
                new_reply_mapping.parent.mkdir(parents=True, exist_ok=True)

                if dry_run:
                    print(f"  [DRY RUN] reply_mapping: {old_reply_mapping} → {new_reply_mapping}")
                else:
                    shutil.copy2(old_reply_mapping, new_reply_mapping)

    return count


def migrate_session_memory_db(matrix_path: str, workspace_root: str, dry_run: bool = False):
    """
    迁移 session_memory.db

    旧路径：{matrix_path}/.matrix/{agent_name}/memory/{user_session_id}/session_memory.db
    新路径：{workspace_root}/.matrix/{agent_name}/{user_session_id}/memory/session_memory.db
    """
    matrix_dir = Path(matrix_path) / ".matrix"

    if not matrix_dir.exists():
        print(f".matrix 目录不存在: {matrix_dir}")
        return 0

    count = 0

    for agent_dir in matrix_dir.iterdir():
        if not agent_dir.is_dir():
            continue

        agent_name = agent_dir.name
        memory_dir = agent_dir / "memory"

        if not memory_dir.exists():
            continue

        # 查找 user_session 子目录
        for item in memory_dir.iterdir():
            if not item.is_dir():
                continue

            # 跳过 global_memory.db 文件
            if item.name.endswith('.db'):
                continue

            user_session_id = item.name
            old_db_path = item / "session_memory.db"

            if not old_db_path.exists():
                continue

            new_db_dir = (
                Path(workspace_root) / ".matrix" / agent_name /
                user_session_id / "memory"
            )
            new_db_path = new_db_dir / "session_memory.db"

            print(f"迁移 memory db: {agent_name}/{user_session_id}")

            if dry_run:
                print(f"  [DRY RUN] {old_db_path} → {new_db_path}")
                count += 1
                continue

            new_db_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_db_path, new_db_path)
            count += 1

    return count


def main():
    import argparse

    parser = argparse.ArgumentParser(description="统一存储路径迁移")
    parser.add_argument("--matrix-path", required=True, help="Matrix 根路径")
    parser.add_argument("--workspace-root", required=True, help="工作区根路径")
    parser.add_argument("--dry-run", action="store_true", help="演练模式")

    args = parser.parse_args()

    print("=" * 60)
    print("统一存储路径迁移")
    print("=" * 60)
    print(f"Matrix 路径: {args.matrix_path}")
    print(f"Workspace 路径: {args.workspace_root}")
    print(f"模式: {'演练（不实际修改）' if args.dry_run else '实际迁移'}")
    print("=" * 60)
    print()

    print("1. 迁移 Session History")
    print("-" * 60)
    history_count = migrate_session_history(args.matrix_path, args.workspace_root, args.dry_run)

    print()
    print("2. 迁移 Session Memory DB")
    print("-" * 60)
    memory_count = migrate_session_memory_db(args.matrix_path, args.workspace_root, args.dry_run)

    print()
    print("=" * 60)
    print("完成！")
    print(f"Session History: {history_count} 个")
    print(f"Session Memory DB: {memory_count} 个")
    if args.dry_run:
        print("\n这是演练模式，没有实际修改文件")
        print("确认无误后，去掉 --dry-run 参数重新运行")
    else:
        print("\n迁移完成！")
        print("建议验证几个文件确保数据正确")
        print("确认无误后，可以删除:")
        print("  - 旧 .matrix/sessions/ 目录")
        print("  - 旧 .matrix/{agent_name}/memory/{user_session_id}/ 目录")
    print("=" * 60)


if __name__ == "__main__":
    main()
