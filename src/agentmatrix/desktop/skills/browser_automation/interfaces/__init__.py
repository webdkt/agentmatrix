"""
Interface 加载器 — 按名字加载前端 interface 目录并拼接为 JS payload。

Interface 目录结构约定：
    interfaces/{name}/
    ├── manifest.json        # 名称、描述、依赖的公共组件
    │   {"name": "...", "description": "...", "requires": ["indicator", "dialog"]}
    └── main.js              # 入口 JS（最后注入）

公共组件目录：
    interfaces/common/
    ├── bridge.js            # 通信协议（始终注入）
    ├── indicator.js         # 指示器组件（按需注入）
    ├── dialog.js            # 对话框组件（按需注入）
    └── selector.js          # 选择框组件（按需注入）
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# interfaces 目录根路径
_INTERFACES_ROOT = Path(__file__).parent


def load_interface(name: str) -> Optional[str]:
    """
    加载一个 interface，返回拼接好的 JS payload。

    加载顺序：
    1. common/bridge.js（始终注入，通信协议）
    2. manifest.json 中 requires 声明的公共组件
    3. interface 自己的 main.js

    Args:
        name: interface 目录名（如 "browser_learning"）

    Returns:
        拼接后的 JS 字符串，如果 interface 不存在则返回 None
    """
    iface_dir = _INTERFACES_ROOT / name
    if not iface_dir.is_dir():
        logger.warning(f"Interface 不存在: {name}")
        return None

    parts = []

    # 1. Bridge（始终注入）
    bridge_js = _read_file(_INTERFACES_ROOT / "common" / "bridge.js")
    if bridge_js:
        parts.append(bridge_js)

    # 2. 读取 manifest 获取依赖
    manifest = _read_manifest(iface_dir / "manifest.json")
    requires = manifest.get("requires", []) if manifest else []

    for comp_name in requires:
        comp_js = _read_file(_INTERFACES_ROOT / "common" / f"{comp_name}.js")
        if comp_js:
            parts.append(comp_js)
        else:
            logger.warning(f"公共组件不存在: {comp_name} (被 {name} 引用)")

    # 3. Interface 自己的 main.js
    main_js = _read_file(iface_dir / "main.js")
    if main_js:
        parts.append(main_js)
    else:
        logger.warning(f"Interface 缺少 main.js: {name}")
        return None

    payload = "\n\n".join(parts)
    logger.info(f"加载 Interface '{name}': {len(payload)} bytes (bridge + {len(requires)} components + main)")
    return payload


def list_interfaces() -> list[dict]:
    """列出所有可用的 interface。"""
    result = []
    for d in sorted(_INTERFACES_ROOT.iterdir()):
        if d.is_dir() and (d / "main.js").exists():
            manifest = _read_manifest(d / "manifest.json")
            result.append({
                "name": d.name,
                "description": manifest.get("description", "") if manifest else "",
                "requires": manifest.get("requires", []) if manifest else [],
            })
    return result


def _read_file(path: Path) -> Optional[str]:
    """读取文件内容。"""
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"读取文件失败 {path}: {e}")
        return None


def _read_manifest(path: Path) -> Optional[dict]:
    """读取 manifest.json。"""
    content = _read_file(path)
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"manifest.json 格式错误 {path}: {e}")
        return None
