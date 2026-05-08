# core/cerebellum.py
import re
import json
import textwrap
from ..core.log_util import AutoLoggerMixin
from .utils import micro_agent_utils as _utils
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.log_config import LogConfig

class Cerebellum(AutoLoggerMixin):
    _custom_log_level = logging.DEBUG

    def __init__(self, backend_client, agent_name: str,
                 parent_logger: Optional[logging.Logger] = None,
                 log_config: Optional['LogConfig'] = None):
        """
        小脑 - 负责参数解析和协商

        Args:
            backend_client: LLM客户端
            agent_name: 所属Agent的名称
            parent_logger: 父组件的logger（用于共享日志）
            log_config: 日志配置
        """
        self.backend = backend_client
        self.agent_name = agent_name

        # 使用父 logger（不创建独立日志文件）
        self._parent_logger = parent_logger
        self._log_config = log_config
        self._log_prefix_template = log_config.prefix if log_config else ""

    async def think(self, messages):
        return await self.backend.think(messages)

    async def convert_params(
        self,
        action_name: str,
        user_params: dict,
        param_schema: dict,
        brain_callback=None,
    ) -> dict:
        """
        参数名对齐 + 通过 Brain 补齐缺失的必要参数。

        循环流程：
        1. 小脑对齐参数名 + 识别缺失
        2. 有缺失 → 问 Brain 输出完整 action 语句
        3. 重新解析 Brain 的回答
        4. 还有缺失 → 继续循环
        5. 全齐 → 返回

        Args:
            action_name: action 名称
            user_params: 用户写出的参数 dict（key 可能不准确，value 原样保留）
            param_schema: 参数定义
            brain_callback: 向 Brain 请求补齐缺失参数的回调

        Returns:
            {"params": {...}, "action_label": "..."}
        """
        # 格式化参数定义
        param_lines = []
        for pname, pmeta in param_schema.items():
            if isinstance(pmeta, dict):
                required = "必填" if pmeta.get("required") else "可选"
                desc = pmeta.get("description", "")
                ptype = pmeta.get("type", "")
                param_lines.append(f"  - {pname} ({ptype}, {required}): {desc}")
            else:
                param_lines.append(f"  - {pname}: {pmeta}")
        param_def = "\n".join(param_lines)

        current_params = dict(user_params)
        action_label = ""
        max_turns = 5

        for turn in range(max_turns):
            # 格式化当前参数名（只给名字，不给值）
            current_keys = ", ".join(current_params.keys()) if current_params else "(无)"

            system_prompt = textwrap.dedent(f"""\
                You are a parameter name aligner.

                Function: {action_name}
                Defined parameters:
                {param_def}

                The user wrote these parameter names: {current_keys}

                Your job:
                1. Map each user parameter name to the correct defined parameter name (case-insensitive, semantic matching)
                2. Identify which required parameters are missing

                Output ONLY a JSON object:
                {{"mapping": {{"user_name1": "correct_name1", ...}}, "missing": ["param1", "param2"], "action_label": "brief description of the purpose of action, NOT what the mapping did"}}
            """)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User wrote these params: {', '.join(current_params.keys())}"},
            ]

            self.logger.debug(f"convert_params turn {turn+1}: {action_name}, params={list(current_params.keys())}")

            response = await self.backend.think(messages=messages)
            raw = response['reply'].replace("```json", "").replace("```", "").strip()

            try:
                alignment = json.loads(raw)
            except json.JSONDecodeError:
                self.logger.warning(f"convert_params JSON 解析失败: {raw[:200]}")
                break

            mapping = alignment.get("mapping", {})
            missing = alignment.get("missing", [])
            action_label = alignment.get("action_label", "")

            # 用 mapping 对齐参数名，value 原样保留
            aligned = {}
            for user_key, user_val in current_params.items():
                correct_key = mapping.get(user_key)
                if isinstance(correct_key, str):
                    aligned[correct_key] = user_val
                # mapping 返回 null/非字符串 → 无法映射，跳过（由调用方过滤）
            current_params = aligned

            # 全齐 → 返回
            if not missing:
                return {"params": current_params, "action_label": action_label}

            # 有缺失但没有 brain_callback → 无法补齐，退出
            if not brain_callback:
                break

            # 问 Brain 补值
            param_names = ", ".join(current_params.keys()) if current_params else "(无)"
            missing_names = ", ".join(missing)
            question = (
                f"你要执行的：{action_name}({param_names})，"
                f"缺少 {missing_names} 参数，请重新输出完整 action 语句"
            )
            answer = await brain_callback(question)
            self.logger.debug(f"[Brain 回复]: {answer}")

            # 从 Brain 回答中提取目标 action 的函数调用
            extracted = self._extract_action_call(answer, action_name)
            if extracted:
                re_parsed = _utils.parse_params_from_call(extracted)
                if re_parsed:
                    current_params.update(re_parsed)

        return {"params": current_params, "action_label": action_label}

    def _extract_action_call(self, text: str, action_name: str) -> str:
        """
        从 Brain 回答中提取目标 action 的函数调用。

        Brain 可能输出额外文字、<action_script> 块等，
        只提取以 action_name 开头的那行完整函数调用。

        Returns:
            函数调用的参数文本（括号内），找不到返回空字符串
        """
        for line in text.splitlines():
            stripped = line.strip()
            # 匹配 action_name( 或 skill.action_name(
            if stripped.startswith(f"{action_name}(") or \
               re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\.' + re.escape(action_name) + r'\(', stripped):
                # 括号配对提取 params
                start = stripped.index('(')
                depth = 1
                pos = start + 1
                while pos < len(stripped) and depth > 0:
                    if stripped[pos] == '(':
                        depth += 1
                    elif stripped[pos] == ')':
                        depth -= 1
                    pos += 1
                if depth == 0:
                    return stripped[start + 1:pos - 1].strip()
        return ""

