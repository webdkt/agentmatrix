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
            attachments: 附件文件列表（容器内路径，例如 ['report.pdf', '/work_files/data.pdf']）
            recipient_name: 收件人 agent 名称
            user_session_id: 用户会话 ID

        Returns:
            附件 metadata 列表

        容器内路径映射规则：
        - 相对路径（如 'report.pdf'）→ 相对于 /work_files
        - /work_files/xxx → work_files 目录下的文件
        - /home/xxx → home 目录下的文件
        """
        workspace_root = self.root_agent.workspace_root
        source_agent = self.root_agent.name

        # 目标目录（收件人的 attachments 目录）
        target_attachments_dir = (
            Path(workspace_root) / "agent_files" / recipient_name / "work_files" / user_session_id / "attachments"
        )

        # 确保目标目录存在
        target_attachments_dir.mkdir(parents=True, exist_ok=True)

        attachment_metadata = []

        for container_path in attachments:
            # 将容器内路径转换为宿主机路径
            host_path = self._resolve_container_path_to_host(container_path, user_session_id)

            if host_path is None or not Path(host_path).exists():
                self.logger.warning(f"附件文件不存在：{container_path} (解析后的宿主机路径: {host_path})")
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
            attachment_metadata.append({
                'filename': filename,
                'size': target_file.stat().st_size,
                'container_path': f'/work_files/attachments/{filename}'
            })

        return attachment_metadata

    def _resolve_container_path_to_host(self, container_path: str, user_session_id: str) -> str:
        """
        将容器内路径转换为宿主机路径

        路径映射规则：
        - 相对路径（如 'report.pdf'）→ 相对于 /work_files
        - /work_files/test.md → {workspace_root}/agent_files/{agent_name}/work_files/{session_id}/test.md
        - /home/plan.md → {workspace_root}/agent_files/{agent_name}/home/plan.md
        - 其他路径 → 直接返回（假设是宿主机路径）

        Args:
            container_path: 容器内路径或宿主机路径
            user_session_id: 用户会话 ID

        Returns:
            宿主机路径
        """
        docker_manager = self.root_agent.docker_manager

        # 非 Docker 环境：直接返回原路径
        if not docker_manager:
            return container_path

        path = Path(container_path)

        # 情况 1: 相对路径（如 'report.pdf'）→ 当作相对于 /work_files
        if not path.is_absolute():
            return str(docker_manager.work_files_base / user_session_id / container_path)

        # 情况 2: /work_files/* → 映射到 work_files 目录
        if container_path.startswith("/work_files/"):
            relative_path = container_path[len("/work_files/"):]
            return str(docker_manager.work_files_base / user_session_id / relative_path)

        # 情况 3: /home/* → 映射到 home 目录
        if container_path.startswith("/home/"):
            relative_path = container_path[len("/home/"):]
            return str(docker_manager.agent_home / relative_path)

        # 情况 4: 其他路径（可能是宿主机路径，直接返回）
        return container_path

