"""
Design Preview Skill — 设计产出的预览 / 提问 / 截图协作 action。

全部 **非阻塞**：每个 action emit 一个 CoreEvent 到前端即立即返回，
结果在下一轮 think 通过现有通道自然回到 LLM：
- refresh_preview：前端 reload 预览 iframe（无需回传）。
- ask_user_question：前端弹表单，用户提交走 user message 通道。
- screenshot_preview：前端截图后 POST 回后端，转 ScreenshotSignal 注入。

注意：本 Mixin 被 SKILL_REGISTRY 动态混入 MicroAgent 子类，
action 执行时 `self` 即 MicroAgent 实例，可直接用 self._emit_event /
self.event_queue / self.root_agent（= DesignCollabAgent）。
"""

from agentmatrix.core.action import register_action


class Design_previewSkillMixin:
    """设计预览协作 action。"""

    _skill_description = (
        "设计预览协作。提供刷新预览、向用户提问、请求预览截图的能力，"
        "配合 DesignCollabAgent 的内嵌预览前端使用。"
    )

    # 事件命名约定：event_type="design"，event_name ∈ {refresh, question, screenshot}
    def _emit_design_event(self, event_name: str, detail: dict):
        """向 DesignCollabAgent 的 event_queue 推一个 design CoreEvent。

        走 MicroAgent 的 _emit_event 助手 —— session_id 由它从 session_store
        固化到 event 上，无需这里处理。
        """
        self._emit_event(
            event_type="design",
            event_name=event_name,
            detail=detail or {},
        )

    @register_action(
        short_desc="(entry_path) 刷新设计预览（写完文件后调用，前端会加载你指定的入口文件，使用相对 current_task的路径）",
        description=(
            "通知前端刷新内嵌预览，加载你刚写出的入口文件。entry_path **必填** —— "
            "前端不知道你把入口写成了什么名字，必须显式告诉它。entry_path 是相对当前 "
            "task 目录的路径，例如 'output/index.html'、'output/Landing Page.html'、"
            "'output/prototypes/v2.html'。省略或空字符串会报错。\n\n"
            "调用后会自动扫描 HTML 生成 output/export.json（PPT 导出按钮会读它）。"
            "完全标准的 deck 结构不会提示；如果检测到 nav chrome / 动画 / 自定义字体等"
            "需要确认的项，返回值里会列出具体要 review 什么。"
        ),
        param_infos={
            "entry_path": "预览入口文件相对路径（必填），如 'output/index.html'"
        },
    )
    async def refresh_preview(self, entry_path: str):
        """刷新预览（fire-and-forget）+ 自动生成 export.json baseline。"""
        if not entry_path or not str(entry_path).strip():
            return (
                "❌ refresh_preview 必须显式提供 entry_path 参数（如 'output/index.html'）。"
                "前端不知道你刚写了什么文件 —— 调用形如 refresh_preview(entry_path=\"output/<你的文件名>\")"
            )
        entry_clean = str(entry_path).strip()
        task_id = getattr(self.root_agent, "current_task_id", None)

        # 拆出 URL 后缀：fragment (#...) 和 query (?...) 不是文件名的一部分，
        # 但对 iframe URL 有用（锚点滚动、查询参数）。文件存在性校验只看 path 部分。
        file_part = entry_clean.split("#", 1)[0].split("?", 1)[0]

        # 校验：必须是相对路径，且相对 current_task 目录确实存在
        from pathlib import Path as _Path

        if _Path(file_part).is_absolute() or file_part.startswith("/"):
            return (
                f"❌ entry_path 必须是相对路径（相对当前 task 目录），收到: {entry_clean!r}。"
                "请改成如 'output/index.html' 的形式。"
            )
        target = None
        task_dir = None
        if task_id and file_part:
            try:
                task_dir = self.root_agent.runtime.paths.get_agent_work_base_dir(
                    self.root_agent.name
                ) / task_id
                target = (task_dir / file_part).resolve()
                # 防穿越：resolve 后必须仍在 task_dir 下
                try:
                    target.relative_to(task_dir.resolve())
                except ValueError:
                    return (
                        f"❌ entry_path 越界（不在当前 task 目录下）: {entry_clean!r}。"
                        "必须是 task 目录内的相对路径。"
                    )
                if not target.exists():
                    return (
                        f"❌ entry_path 对应的文件不存在: {entry_clean!r}\n"
                        f"  期望位置: {target}\n"
                        "请确认文件已经写出，或路径写错了。可以先用 file skill 列目录核对。"
                    )
            except Exception:
                # runtime/paths 异常时不要阻断 emit（让前端按既有逻辑跑），但记 warning
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "[DesignPreview] refresh_preview 路径校验异常: %s", entry_clean, exc_info=True
                )

        # 持久化到 session metadata —— 切换 session 时 DesignCollabAgent 会读这里
        # 再 emit 一次 refresh 事件，让前端能恢复预览入口（不用查 events）。
        session = getattr(self.root_agent, "current_session", None)
        if session is not None:
            session.setdefault("metadata", {})["preview_entry_path"] = entry_clean

        self._emit_event(
            event_type="design",
            event_name="refresh",
            detail={
                "task_id": task_id,
                "entry_path": entry_clean,
                "preview_port": getattr(self.root_agent, "preview_port", None),
            },
        )

        # ---- 自动生成 export.json baseline（确定性字段走代码，非确定项给 agent 提示） ----
        export_note = self._auto_gen_export_config(
            html_path=target,
            entry_path_rel=entry_clean,
            task_dir=task_dir,
        )

        if export_note:
            return f"已通知前端刷新预览到 {entry_path}\n\n{export_note}"
        return f"已通知前端刷新预览到 {entry_path}"

    def _auto_gen_export_config(self, html_path, entry_path_rel: str, task_dir) -> str:
        """调 pptx_export.auto_config 生成 baseline export.json，返回给 agent 的提示文本。

        纯字符串拼装，不抛异常。任何失败都转成对 agent 友好的提示。
        返回 '' 表示「完全确定，无需提示 agent」（tier 0）。
        """
        if html_path is None or task_dir is None:
            return ""  # 路径校验环节出问题，跳过自动生成
        try:
            from pathlib import Path as _P
            from .pptx_export.auto_config import analyze_html_for_export

            out_dir = _P(task_dir) / "output"
            report = analyze_html_for_export(
                html_path=_P(html_path),
                entry_path_rel=entry_path_rel,
                out_dir=out_dir,
            )
        except Exception as e:
            # 自动生成失败不阻塞预览，但要让 agent 知道导出按钮会报错
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "[DesignPreview] auto_config 异常: %s", e, exc_info=True
            )
            return (
                f"⚠️ 自动生成 export.json 失败: {e}\n"
                "预览正常，但 PPT 导出按钮会报错。可以让 Designer 手写 output/export.json，"
                "或忽略（如果不需要导出 PPT）。"
            )

        # tier 0：完全确定，对 agent 静默
        if report.tier == 0 and report.ok:
            return ""

        # tier 3：无法识别 slide 结构
        if not report.ok:
            return (
                f"⚠️ 自动生成 export.json 失败：{report.error}\n\n"
                "预览正常，但 PPT 导出按钮会报错（没有 export.json）。"
            )

        # tier 1 / 2：列出 hints
        if not report.hints:
            return ""
        bullets = "\n".join(f"  - {h}" for h in report.hints)
        path_line = (
            f"（已生成 {report.config_path}）\n"
            if report.config_path else "（export.json 未写盘）\n"
        )
        review_line = (
            "请 review 以下几点（baseline 已给默认值，导出能跑；若不对请改 JSON 对应字段）："
            if report.tier == 2 else
            "提示："
        )
        return f"📐 PPT 导出配置已自动生成。{path_line}{review_line}\n{bullets}"

    @register_action(
        short_desc="向用户提问（非阻塞，答案会在下一轮作为用户消息回来）",
        description=(
            "向用户提出澄清问题。questions 是问题列表，每项形如 "
            '{"question":"...","options":["A","B"],"multi_select":false,"default":"A"}。'
            "调用后立即返回，不要在同一轮期待答案 —— 用户回答后会在下一轮对话中出现。"
        ),
        param_infos={
            "questions": "问题列表（JSON 字符串或 list），每项含 question/options/multi_select/default"
        },
    )
    async def ask_user_question(self, questions):
        """向用户提问（非阻塞）。"""
        # 容忍 LLM 传 JSON 字符串
        if isinstance(questions, str):
            import json

            try:
                questions = json.loads(questions)
            except Exception:
                questions = [{"question": questions}]
        if not isinstance(questions, list):
            questions = [{"question": str(questions)}]

        self._emit_design_event("question", {"questions": questions})
        return "已向用户提问，等待回复（答案将在下一轮对话中到达）"

    @register_action(
        short_desc="截图当前预览，保存为文件，后续可用视觉功能查看",
        description=(
            "用后端 headless Chrome 渲染当前预览并截图，落盘后返回容器内路径。"
            "拿到路径后调 look(path) 即可在同一轮对话里查看截图，用视觉能力核对布局。"
            "截图前请确保已用 refresh_preview 指定 entry_path，否则默认截 output/index.html。"
        ),
        param_infos={},
    )
    async def screenshot_preview(self):
        """同步截图，返回文件路径。"""
        agent = self.root_agent
        task_id = getattr(agent, "current_task_id", None)
        session = getattr(agent, "current_session", None) or {}
        metadata = session.get("metadata") or {}
        entry_path = metadata.get("preview_entry_path")

        if not task_id:
            return "❌ 当前没有 active task，无法截图"
        url = agent.get_preview_url(task_id, entry_path)
        if not url:
            return (
                "❌ 预览 server 未启动 / URL 解析失败。请稍后再试，"
                "或先用 refresh_preview 指定入口文件。"
            )

        path = await agent.take_preview_screenshot(url=url)
        if not path:
            return f"❌ 截图失败：{url}（看后端日志排查 Playwright 是否启动成功）"
        return (
            f"截图已保存：{path}\n"
            f"预览 URL：{url}\n"
            f"调用 look(\"{path}\") 即可查看这张图。"
        )
