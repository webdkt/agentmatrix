"""
Memory Skill 工具函数

职责：
- Profile 格式化
- Profile 分批算法
- Whiteboard 文件管理
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Callable

# 从通用工具导入
from ...utils.token_utils import estimate_tokens, format_conversation_messages


# ==================== Profile 格式化 ====================

def format_profile_card(profile: Dict[str, Any]) -> str:
    """
    格式化单个 profile 为档案卡片

    格式：
    ## 档案卡片：{canonical_name}

    [别名]
    {alias list}

    [档案]
    {profile_text}

    （以上内容最后更新于：{date}）

    Args:
        profile: 合并后的 profile，包含:
            - canonical_name: str
            - session_profile: dict or None
            - longterm_profile: dict or None

    Returns:
        str: 格式化的档案卡片文本
    """
    import json

    lines = []

    canonical_name = profile['canonical_name']
    session_p = profile.get('session_profile')
    longterm_p = profile.get('longterm_profile')

    # 标题
    lines.append(f"## 档案卡片：{canonical_name}")

    # 合并别名（从 session 和 global）
    aliases = set()
    if session_p and session_p.get('aliases'):
        try:
            aliases.update(json.loads(session_p['aliases']))
        except:
            pass
    if longterm_p and longterm_p.get('aliases'):
        try:
            aliases.update(json.loads(longterm_p['aliases']))
        except:
            pass

    if aliases:
        lines.append("\n[别名]")
        lines.append(", ".join(sorted(aliases)))

    # 合并档案内容（不区分全局和会话，直接合并）
    profile_texts = []
    latest_date = None

    if longterm_p:
        profile_texts.append(longterm_p['profile_text'])
        updated_at = longterm_p.get('updated_at', '')
        if updated_at:
            date_str = updated_at.split(' ')[0]
            if not latest_date or date_str > latest_date:
                latest_date = date_str

    if session_p:
        profile_texts.append(session_p['profile_text'])
        updated_at = session_p.get('updated_at', '')
        if updated_at:
            date_str = updated_at.split(' ')[0]
            if not latest_date or date_str > latest_date:
                latest_date = date_str

    if profile_texts:
        lines.append("\n[档案]")
        lines.append("\n\n".join(profile_texts))

        # 添加最后更新日期
        if latest_date:
            lines.append(f"\n（以上内容最后更新于：{latest_date}）")

    return "\n".join(lines)


def format_profiles_batch(profiles: List[Dict[str, Any]]) -> str:
    """
    格式化一批 profiles 为文本

    Args:
        profiles: profile 列表

    Returns:
        str: 批量格式化的档案卡片，用分隔符分开
    """
    cards = []
    for profile in profiles:
        card = format_profile_card(profile)
        cards.append(card)

    return "\n\n------\n\n".join(cards)  # 用 ------ 分隔不同的卡片


# ==================== Profile 分批算法 ====================

def split_profiles_by_tokens(
    profiles: List[Dict[str, Any]],
    token_limit: int,
    format_func: Callable[[Dict[str, Any]], str] = format_profile_card
) -> List[List[Dict[str, Any]]]:
    """
    按 token 预估算分批

    Args:
        profiles: profile 列表
        token_limit: 每个 batch 的 token 上限
        format_func: 格式化函数（用于估算 token）

    Returns:
        分批后的 profile 列表（二维列表）
    """
    batches = []
    current_batch = []
    current_tokens = 0

    for profile in profiles:
        # 估算这个 profile 的 tokens
        profile_text = format_func(profile)
        estimated_tokens = estimate_tokens(profile_text)

        # 如果单个 profile 就超过限制，单独一批
        if estimated_tokens > token_limit:
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            batches.append([profile])
            continue

        # 如果加上这个 profile 会超限，先保存当前 batch
        if current_tokens + estimated_tokens > token_limit:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        # 加入当前 batch
        current_batch.append(profile)
        current_tokens += estimated_tokens

    # 最后一个 batch
    if current_batch:
        batches.append(current_batch)

    return batches


# ==================== Whiteboard 文件管理 ====================

def get_whiteboard_path(workspace_root: str, agent_name: str,
                        user_session_id: str) -> str:
    """
    获取 whiteboard.md 文件路径

    Args:
        workspace_root: 工作区根目录
        agent_name: Agent 名称
        user_session_id: 用户会话 ID

    Returns:
        str: whiteboard.md 文件的完整路径
    """
    return os.path.join(
        workspace_root,
        ".matrix",
        agent_name,
        "memory",
        user_session_id,
        "whiteboard.md"
    )


def load_whiteboard(workspace_root: str, agent_name: str,
                   user_session_id: str) -> str:
    """
    加载 whiteboard 内容

    Args:
        workspace_root: 工作区根目录
        agent_name: Agent 名称
        user_session_id: 用户会话 ID

    Returns:
        str: whiteboard 内容（如果文件不存在则返回空字符串）
    """
    path = get_whiteboard_path(workspace_root, agent_name, user_session_id)

    if not os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_whiteboard(content: str, workspace_root: str, agent_name: str,
                   user_session_id: str) -> bool:
    """
    保存 whiteboard 内容

    Args:
        content: whiteboard 内容（Markdown 格式）
        workspace_root: 工作区根目录
        agent_name: Agent 名称
        user_session_id: 用户会话 ID

    Returns:
        bool: 是否保存成功
    """
    path = get_whiteboard_path(workspace_root, agent_name, user_session_id)

    # 确保目录存在
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return True
