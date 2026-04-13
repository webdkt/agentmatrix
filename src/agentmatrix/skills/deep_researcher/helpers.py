"""
Research Planner Helpers

- format_prompt() 工具函数
- SQLite note 数据库操作函数
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional

from ...skills.parser_utils import extract_json, validate_json_fields


# ==========================================
# Prompt 格式化工具
# ==========================================


def format_prompt(prompt: str, context=None, **kwargs) -> str:
    """
    根据 context 对象/字典和 kwargs 填充 prompt 占位符

    优先级: kwargs > context
    """
    placeholders = re.findall(r"\{(\w+)\}", prompt)
    format_dict = {}
    missing = []

    for p in placeholders:
        if p in kwargs:
            format_dict[p] = kwargs[p]
        elif isinstance(context, dict) and p in context:
            format_dict[p] = context[p]
        elif context is not None and hasattr(context, p):
            format_dict[p] = getattr(context, p)
        else:
            missing.append(p)

    if missing:
        raise KeyError(f"缺少以下占位符: {', '.join(missing)}")

    return prompt.format(**format_dict)


# ==========================================
# SQLite Note 数据库操作
# ==========================================


def init_note_db(db_path: str):
    """创建 notes 表（如果不存在）"""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_text TEXT NOT NULL,
            chapter_name TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def normalize_tags(tags_input: str) -> str:
    """
    标准化 tags：小写、去特殊字符、排序、最多3个，逗号包裹存储格式

    输出格式：,tag1,tag2,tag3,
    空 tags 返回空字符串 ""。

    规则：
    - 全部小写
    - 空格和下划线转连字符
    - 只保留字母数字和连字符
    - 去除连续连字符和首尾连字符
    - 去重后按字母排序
    - 最多保留3个
    """
    if not tags_input:
        return ""

    raw_tags = [t.strip().lower() for t in tags_input.split(",") if t.strip()]

    clean_tags = []
    for tag in raw_tags:
        # 空格和下划线转连字符
        tag = tag.replace(" ", "-").replace("_", "-")
        # 只保留字母数字、汉字和连字符
        clean = re.sub(r"[^a-z0-9\u4e00-\u9fff\-]", "", tag)
        # 去除连续连字符
        clean = re.sub(r"-+", "-", clean)
        # 去除首尾连字符
        clean = clean.strip("-")
        if clean:
            clean_tags.append(clean)

    # 去重、排序
    clean_tags = sorted(set(clean_tags))
    # 最多3个，逗号包裹格式：,tag1,tag2,tag3,
    if not clean_tags:
        return ""
    return "," + ",".join(clean_tags[:3]) + ","


def insert_note(db_path: str, note_text: str, chapter_name: str = "", tags: str = "") -> int:
    """插入 note，返回 ID"""
    init_note_db(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "INSERT INTO notes (note_text, chapter_name, tags) VALUES (?, ?, ?)",
        (note_text, chapter_name, tags),
    )
    note_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return note_id


def search_notes_by_keyword(db_path: str, query: str) -> list:
    """单关键词全文搜索，返回全部结果（给 search_note_w_keyword action 用）"""
    return search_notes_by_keywords(db_path, [query])


def search_notes_by_keywords(db_path: str, keywords: list, limit: int = 0) -> list:
    """
    多关键词 AND 搜索 note_text 和 tags，返回匹配结果

    每个 keyword 必须在 note_text（LIKE）或 tags（标准化后精确匹配）中命中。
    所有 keywords 之间是 AND 关系。按 ID 倒序排列（新的在前）。

    Args:
        db_path: 数据库路径
        keywords: 关键词列表
        limit: 结果数量限制，0 表示不限制
    """
    if not keywords or not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)

    conditions = []
    params = []
    for kw in keywords:
        kw_lower = kw.lower().strip()
        if not kw_lower:
            continue
        normalized = normalize_tags(kw).strip(",")
        tag_pattern = f"%,{normalized},%"
        text_pattern = f"%{kw}%"
        conditions.append("(note_text LIKE ? OR tags LIKE ?)")
        params.extend([text_pattern, tag_pattern])

    if not conditions:
        conn.close()
        return []

    where = " AND ".join(conditions)
    limit_clause = f"LIMIT {limit}" if limit > 0 else ""

    results = conn.execute(
        f"""
        SELECT id, note_text, chapter_name, tags
        FROM notes
        WHERE {where}
        ORDER BY id DESC
        {limit_clause}
        """,
        params,
    ).fetchall()

    conn.close()
    return results
    return results


def find_similar_notes(db_path: str, tags_str: str) -> list:
    """
    查找与给定 tags 满足双向超集关系的 notes

    双向超集：新 tags 和已有 tags，其中一方是另一方的子集（即有包含关系）。
    例：a,b,x 和 ,a,b,d,e,x,y, 命中（后者是前者的超集）
        ,a,b,x,y,z, 和 a,b,x 命中（前者是后者的超集）
        a,b,x 和 a,b 命中（{a,b} ⊂ {a,b,x}）

    实现：SQL 用 ,tag, 格式宽松捞有 tag 交集的 candidates，Python 侧做集合判断。
    tags 存储格式：,tag1,tag2,tag3,
    """
    if not tags_str or not Path(db_path).exists():
        return []

    # tags_str 可能是 normalize_tags 的输出（,a,b,x,）或原始输入（a,b,x）
    raw = tags_str.strip(",")
    new_tags_set = set(t.strip() for t in raw.split(",") if t.strip())
    if not new_tags_set:
        return []

    conn = sqlite3.connect(db_path)

    # 宽松捞：任一 tag 出现在 note 的 tags 中就候选
    conditions = []
    params = []
    for tag in new_tags_set:
        conditions.append("tags LIKE ?")
        params.append(f"%,{tag},%")

    where = " OR ".join(conditions)
    candidates = conn.execute(
        f"SELECT id, note_text, chapter_name, tags FROM notes WHERE {where}",
        params,
    ).fetchall()
    conn.close()

    # Python 侧过滤：双向超集（一方是另一方的子集）
    results = []
    for row in candidates:
        existing_raw = row[3].strip(",") if row[3] else ""
        existing_tags = set(t.strip() for t in existing_raw.split(",") if t.strip())
        if not existing_tags:
            continue
        if new_tags_set.issubset(existing_tags) or existing_tags.issubset(new_tags_set):
            results.append(row)

    return results


def get_notes_by_chapter(db_path: str, chapter_name: str) -> list:
    """获取某 chapter 的所有 notes"""
    if not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)
    results = conn.execute(
        "SELECT id, note_text, chapter_name, tags FROM notes WHERE chapter_name = ? ORDER BY id",
        (chapter_name,),
    ).fetchall()
    conn.close()
    return results


def fix_all_note_tags(db_path: str) -> int:
    """标准化数据库中所有 notes 的 tags，返回修复的条数"""
    if not Path(db_path).exists():
        return 0

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, tags FROM notes").fetchall()
    fixed = 0
    for note_id, raw_tags in rows:
        if not raw_tags:
            continue
        normalized = normalize_tags(raw_tags)
        if normalized != raw_tags:
            conn.execute("UPDATE notes SET tags = ? WHERE id = ?", (normalized, note_id))
            fixed += 1
    conn.commit()
    conn.close()
    return fixed


def get_all_notes(db_path: str) -> list:
    """获取所有 notes"""
    if not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)
    results = conn.execute(
        "SELECT id, note_text, chapter_name, tags FROM notes ORDER BY id"
    ).fetchall()
    conn.close()
    return results


# ==========================================
# Parser 函数（配合 think_with_retry 使用）
# ==========================================


def duplicate_check_parser(raw_reply: str) -> dict:
    """
    解析去重检查的 JSON 输出

    期望格式：{"duplicate": bool, "duplicate_id": int|null, "reason": str}
    """
    data, err = extract_json(raw_reply)
    if err:
        return {"status": "error", "feedback": err}

    err = validate_json_fields(data, {
        "duplicate": (bool, "'duplicate' 必须是 true/false"),
    })
    if err:
        return {"status": "error", "feedback": err}

    if data["duplicate"]:
        dup_id = data.get("duplicate_id")
        if dup_id is not None and not isinstance(dup_id, int):
            return {"status": "error", "feedback": "'duplicate_id' 必须是整数或 null"}

    return {
        "status": "success",
        "content": {
            "duplicate": data["duplicate"],
            "duplicate_id": data.get("duplicate_id"),
            "reason": data.get("reason", ""),
        },
    }


def nl_search_answer_parser(raw_reply: str) -> dict:
    """
    解析自然语言搜索的 JSON 判断输出

    期望格式：{"answered": bool, "answer": str, "useful_ids": [int, ...]}
    """
    data, err = extract_json(raw_reply)
    if err:
        return {"status": "error", "feedback": err}

    err = validate_json_fields(data, {
        "answered": (bool, "'answered' 必须是 true/false"),
        "answer": (str, "'answer' 必须是字符串"),
        "useful_ids": (list, "'useful_ids' 必须是数组"),
    })
    if err:
        return {"status": "error", "feedback": err}

    # 校验 useful_ids 中的元素
    useful_ids = []
    for x in data["useful_ids"]:
        if not isinstance(x, int):
            return {"status": "error", "feedback": "useful_ids 中的每个元素必须是整数"}
        useful_ids.append(x)

    return {
        "status": "success",
        "content": {
            "answered": data["answered"],
            "answer": data["answer"],
            "useful_ids": useful_ids,
        },
    }
