"""
Email Skill - 邮件相关 Actions

提供邮件发送功能：
- send_email: 发送邮件给同事（支持附件）

未来可以扩展：
- check_email: 检查邮件
- read_email: 读取邮件详情
"""

import shutil
from pathlib import Path
from typing import Any, List
from ...core.action import register_action


class EmailSkillMixin:
    """
    Email Actions

    提供邮件发送功能（未来可扩展邮件检查、读取等功能）
    """

    # 🆕 Skill 级别元数据
    _skill_description = (
        "邮件发送技能：向其他 Agent 发送邮件，支持附件. 名字就是邮件地址"
    )

    _skill_usage_guide = """
使用场景：
- 需要与其他 Agent 沟通
- 需要传输文件或数据给其他 Agent
- 需要跨 Agent 协作

使用建议：
- 使用 send_email 发送邮件
- 支持附带附件（容器内路径）
- 主题如果不填会自动截取 body 的前20个字

注意事项：
- 这是与其他 Agent 沟通的唯一方式
- 附件会自动复制到收件人的 attachments 目录
"""

    @register_action(
        short_desc="发邮件给用户和其他Agent，名字即地址",
        description="发邮件给同事，这是和其他人沟通的唯一方式。可以附带附件文件。",
        param_infos={
            "to": "收件人 (e.g. 'User')",
            "body": "邮件内容",
            "subject": "邮件主题 (可选，如果不填，系统会自动截取 body 的前20个字)",
            "attachments": "附件文件列表（容器内路径，例如 ['report.pdf', '~/current_task/data.pdf']，可选）",
        },
    )
    async def send_internal_mail(
        self, to: str, body: str, subject: str = None, attachments: List[str] = None
    ):
        """
        发送邮件给同事（支持附件）

        Args:
            to: 收件人名称
            body: 邮件内容
            subject: 邮件主题（可选）
            attachments: 附件文件列表（容器内路径，例如 ['report.pdf']）

        邮件路由逻辑：
        - 如果发给 session 的 original_sender：in_reply_to = session.session_id
        - 如果发给 last_email.sender：in_reply_to = last_email.id
        - 否则：in_reply_to = session.session_id

        附件处理：
        - 从当前 agent 的 attachments 目录复制到目标 agent 的 attachments 目录
        - 自动处理文件重名
        """
        # 校验收件人是否为有效的系统 Agent 名字
        runtime = self.root_agent.runtime
        if runtime and runtime.agent_name_set:
            if to not in runtime.agent_name_set:
                return f"内部邮箱收件人地址错误，请使用Agent名字作为收件地址。当前系统Agent：{', '.join(sorted(runtime.agent_name_set))}"
        # 导入 Email 类（避免循环导入）
        from ...core.message import Email

        # 获取当前 session 和最后收到的邮件（从 root_agent 获取）
        # 注意：MicroAgent 自身不发送邮件，只有 BaseAgent 发送
        session = self.root_agent.current_session
        last_email = self.root_agent.last_received_email

        # 确定 in_reply_to
        # 使用 last_email.id 关联回话线程；如果没有上一封邮件则为 None（新会话）
        in_reply_to = last_email.id if last_email else None

        # 自动生成 subject（如果未提供）
        if not subject:
            # 如果 body 很短，直接用 body 做 subject
            # 如果 body 很长，截取前 20 个字 + ...
            clean_body = body.strip().replace("\n", " ")
            subject = clean_body[:20] + "..." if len(clean_body) > 20 else clean_body

        # 处理附件
        attachment_metadata = []
        if attachments:
            attachment_metadata = await self._copy_attachments_to_recipient(
                attachments=attachments, recipient_name=to, task_id=session["task_id"]
            )

        # 构造邮件
        msg = Email(
            sender=self.root_agent.name,  # 发送者是 BaseAgent
            recipient=to,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
            task_id=session["task_id"],
            sender_session_id=session["session_id"],  # 🆕 发件人的 session
            recipient_session_id=None,  # 收件人的 session（由收件人收到后更新）
            metadata={"attachments": attachment_metadata}
            if attachment_metadata
            else {},
        )

        # 发送邮件（通过 root_agent 的 post_office）
        await self.root_agent.post_office.dispatch(msg)

        # 更新 reply_mapping（自动保存到磁盘，通过 root_agent 的 session_manager）
        await self.root_agent.session_manager.update_reply_mapping(
            msg_id=msg.id,
            session_id=session["session_id"],  # 使用已获取的 session 变量
            task_id=session["task_id"],
        )

        # 返回成功信息
        if attachment_metadata:
            filenames = [att["filename"] for att in attachment_metadata]
            return f"邮件已发送给 {to}，附件：{', '.join(filenames)}"
        return f"邮件已发送给 {to}"

    async def _copy_attachments_to_recipient(
        self, attachments: List[str], recipient_name: str, task_id: str
    ) -> List[dict]:
        """
        复制附件到目标 agent 的 attachments 目录

        Args:
            attachments: 附件文件列表（容器内路径，例如 ['report.pdf', '~/current_task/data.pdf']）
            recipient_name: 收件人 agent 名称
            task_id: 用户会话 ID

        Returns:
            附件 metadata 列表

        容器内路径映射规则：
        - 相对路径（如 'report.pdf'）→ 基于当前任务目录
        - ~/current_task/xxx → 当前任务目录下的文件
        - /data/agents/{username}/home/xxx → home 目录下的文件
        """
        if self.root_agent.runtime is None:
            raise ValueError("runtime 未注入，无法发送附件")

        source_agent = self.root_agent.name

        # 目标目录（收件人的 attachments 目录）
        target_attachments_dir = (
            self.root_agent.runtime.paths.get_agent_attachments_dir(
                recipient_name, task_id
            )
        )

        # 确保目标目录存在
        target_attachments_dir.mkdir(parents=True, exist_ok=True)

        attachment_metadata = []

        for container_path in attachments:
            # 将容器内路径转换为宿主机路径
            host_path = self._resolve_container_path_to_host(container_path, task_id)

            if host_path is None or not Path(host_path).exists():
                self.logger.warning(
                    f"附件文件不存在：{container_path} (解析后的宿主机路径: {host_path})"
                )
                continue

            # 从容器路径提取文件名
            filename = Path(container_path).name
            source_file = Path(host_path)

            # 目标文件路径（同名文件直接覆盖）
            target_file = target_attachments_dir / filename

            # 复制文件
            shutil.copy2(source_file, target_file)
            self.logger.info(f"附件已复制：{source_file} -> {target_file}")

            # 添加到 metadata
            attachment_metadata.append(
                {
                    "filename": filename,
                    "size": target_file.stat().st_size,
                    "container_path": f"~/current_task/attachments/{filename}",
                }
            )

        return attachment_metadata

    def _resolve_container_path_to_host(self, container_path: str, task_id: str) -> str:
        """
        将容器内路径转换为宿主机路径

        路径映射规则：
        - 相对路径（如 'report.pdf'）→ 基于当前任务目录
        - ~/current_task/... → 基于当前任务目录
        - /data/agents/{username}/... → workspace/agent_files/{username}/...

        Args:
            container_path: 容器内路径或宿主机路径
            task_id: 用户会话 ID

        Returns:
            宿主机路径
        """
        runtime = self.root_agent.runtime
        if not runtime:
            return container_path

        agent_name = self.root_agent.name
        path = Path(container_path)

        # 情况 1: 相对路径 → 基于当前任务目录
        if not path.is_absolute():
            return str(
                runtime.paths.get_agent_work_files_dir(agent_name, task_id)
                / container_path
            )

        # 情况 2: ~/current_task/... 展开为绝对路径
        if container_path.startswith("~"):
            rel = container_path.lstrip("~/")
            return str(
                runtime.paths.get_agent_work_files_dir(agent_name, task_id) / rel
            )

        # 情况 3: /data/agents/{username}/... → workspace/agent_files/{username}/...
        if container_path.startswith("/data/agents/"):
            relative = container_path.split("/data/agents/")[1]
            return str(runtime.paths.workspace_dir / "agent_files" / relative)

        # 情况 4: 其他绝对路径（可能是宿主机路径，直接返回）
        return container_path
