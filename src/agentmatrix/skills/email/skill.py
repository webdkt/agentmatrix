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
    _skill_description = "邮件发送技能：向其他 Agent 发送邮件，支持附件"

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
        "发邮件给同事，这是和其他人沟通的唯一方式。可以附带附件文件。",
        param_infos={
            "to": "收件人 (e.g. 'User')",
            "body": "邮件内容",
            "subject": "邮件主题 (可选，如果不填，系统会自动截取 body 的前20个字)",
            "attachments": "附件文件列表（容器内路径，例如 ['/work_files/report.pdf']，可选）"
        }
    )
    async def send_email(
        self,
        to: str,
        body: str,
        subject: str = None,
        attachments: List[str] = None
    ):
        """
        发送邮件给同事（支持附件）

        Args:
            to: 收件人名称
            body: 邮件内容
            subject: 邮件主题（可选）
            attachments: 附件文件列表（容器内路径，例如 ['/work_files/report.pdf']）

        邮件路由逻辑：
        - 如果发给 session 的 original_sender：in_reply_to = session.session_id
        - 如果发给 last_email.sender：in_reply_to = last_email.id
        - 否则：in_reply_to = session.session_id

        附件处理：
        - 从当前 agent 的 attachments 目录复制到目标 agent 的 attachments 目录
        - 自动处理文件重名
        """
        # 导入 Email 类（避免循环导入）
        from ...core.message import Email

        # 获取当前 session 和最后收到的邮件（从 root_agent 获取）
        # 注意：MicroAgent 自身不发送邮件，只有 BaseAgent 发送
        session = self.root_agent.current_session
        last_email = self.root_agent.last_received_email

        # 确定 in_reply_to
        in_reply_to = session["session_id"]
        if to == last_email.sender:
            in_reply_to = last_email.id

        # 自动生成 subject（如果未提供）
        if not subject:
            # 如果 body 很短，直接用 body 做 subject
            # 如果 body 很长，截取前 20 个字 + ...
            clean_body = body.strip().replace('\n', ' ')
            subject = clean_body[:20] + "..." if len(clean_body) > 20 else clean_body

        # 处理附件
        attachment_metadata = []
        if attachments:
            attachment_metadata = await self._copy_attachments_to_recipient(
                attachments=attachments,
                recipient_name=to,
                user_session_id=session["user_session_id"]
            )

        # 构造邮件
        msg = Email(
            sender=self.root_agent.name,  # 发送者是 BaseAgent
            recipient=to,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
            user_session_id=session["user_session_id"],
            metadata={'attachments': attachment_metadata} if attachment_metadata else {}
        )

        # 发送邮件（通过 root_agent 的 post_office）
        await self.root_agent.post_office.dispatch(msg)

        # 更新 reply_mapping（自动保存到磁盘，通过 root_agent 的 session_manager）
        await self.root_agent.session_manager.update_reply_mapping(
            msg_id=msg.id,
            session_id=session["session_id"],  # 使用已获取的 session 变量
            user_session_id=session["user_session_id"]
        )

        # 返回成功信息
        if attachment_metadata:
            filenames = [att['filename'] for att in attachment_metadata]
            return f"邮件已发送给 {to}，附件：{', '.join(filenames)}"
        return f"邮件已发送给 {to}"

    async def _copy_attachments_to_recipient(
        self,
        attachments: List[str],
        recipient_name: str,
        user_session_id: str
    ) -> List[dict]:
        """
        复制附件到目标 agent 的 attachments 目录

        Args:
            attachments: 附件文件列表（容器内路径，例如 ['/work_files/report.pdf']）
            recipient_name: 收件人 agent 名称
            user_session_id: 用户会话 ID

        Returns:
            附件 metadata 列表
        """
        workspace_root = self.root_agent.workspace_root
        source_agent = self.root_agent.name

        # 构建源和目标目录
        source_attachments_dir = (
            Path(workspace_root) / "agent_files" / source_agent / "work_files" / user_session_id / "attachments"
        )
        target_attachments_dir = (
            Path(workspace_root) / "agent_files" / recipient_name / "work_files" / user_session_id / "attachments"
        )

        # 确保目标目录存在
        target_attachments_dir.mkdir(parents=True, exist_ok=True)

        attachment_metadata = []

        for container_path in attachments:
            # 从容器内路径提取文件名：/work_files/report.pdf -> report.pdf
            filename = Path(container_path).name

            # 源文件路径（宿主机）
            source_file = source_attachments_dir / filename

            # 检查源文件是否存在
            if not source_file.exists():
                self.logger.warning(f"附件文件不存在：{source_file}")
                continue

            # 目标文件路径（同名文件直接覆盖）
            target_file = target_attachments_dir / filename

            # 复制文件
            shutil.copy2(source_file, target_file)
            self.logger.info(f"附件已复制：{source_file} -> {target_file}")

            # 添加到 metadata
            attachment_metadata.append({
                'filename': filename,
                'size': target_file.stat().st_size,
                'container_path': f'/work_files/attachments/{filename}'
            })

        return attachment_metadata

