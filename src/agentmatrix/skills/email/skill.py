"""
Email Skill - 邮件相关 Actions

提供邮件发送功能：
- send_email: 发送邮件给同事（支持附件）

未来可以扩展：
- check_email: 检查邮件
- read_email: 读取邮件详情
"""

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Tuple
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
        attachment_errors = []
        if attachments:
            attachment_metadata, attachment_errors = await self._copy_attachments_to_recipient(
                attachments=attachments, recipient_name=to, task_id=session["task_id"]
            )

            # 附件全部失败则中止发送
            if attachment_errors and not attachment_metadata:
                return "邮件发送失败：" + "; ".join(attachment_errors)

        # 构造邮件
        msg = Email(
            sender=self.root_agent.name,  # 发送者是 BaseAgent
            recipient=to,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
            task_id=session["task_id"],
            sender_session_id=session["session_id"],  # 🆕 发件人的 session
            recipient_session_id=last_email.sender_session_id if last_email else None,
            metadata={"attachments": attachment_metadata}
            if attachment_metadata
            else {},
        )

        # 发送邮件（通过 root_agent 的 post_office）
        await self.root_agent.post_office.dispatch(msg)

        # 📝 写入 session event: email.sent
        body_preview = body[:200] if body else None
        await self._log_event("email", "sent", {
            "email_id": msg.id,
            "subject": subject,
            "body_preview": body_preview,
            "sender": self.root_agent.name,
            "recipient": to,
            "has_more": len(body) > 200 if body else False,
            "attachments": [att.get("filename") for att in attachment_metadata] if attachment_metadata else [],
        })

        # 更新 reply_mapping（自动保存到磁盘，通过 root_agent 的 session_manager）
        await self.root_agent.session_manager.update_reply_mapping(
            msg_id=msg.id,
            session_id=session["session_id"],  # 使用已获取的 session 变量
            task_id=session["task_id"],
        )

        # 返回成功信息
        result_parts = []
        if attachment_metadata:
            filenames = [att["filename"] for att in attachment_metadata]
            result_parts.append(f"邮件已发送给 {to}，附件：{', '.join(filenames)}")
        else:
            result_parts.append(f"邮件已发送给 {to}")

        if attachment_errors:
            result_parts.append("部分附件失败：" + "; ".join(attachment_errors))

        return "\n".join(result_parts)

    async def _copy_attachments_to_recipient(
        self, attachments: List[str], recipient_name: str, task_id: str
    ) -> Tuple[List[dict], List[str]]:
        """
        复制附件到目标 agent 的 attachments 目录

        Args:
            attachments: 附件文件列表（容器内路径，例如 ['report.pdf', '~/current_task/data.pdf']）
            recipient_name: 收件人 agent 名称
            task_id: 用户会话 ID

        Returns:
            (attachment_metadata, errors): 附件 metadata 列表和错误信息列表

        容器内路径映射规则：
        - 相对路径（如 'report.pdf'）→ 基于当前任务目录
        - ~/current_task/xxx → 当前任务目录下的文件
        - /data/agents/{username}/home/xxx → home 目录下的文件
        - 其他绝对路径（如 /tmp/xxx）→ 从容器内提取
        """
        if self.root_agent.runtime is None:
            raise ValueError("runtime 未注入，无法发送附件")

        # 目标目录（收件人的 attachments 目录）
        target_attachments_dir = (
            self.root_agent.runtime.paths.get_agent_attachments_dir(
                recipient_name, task_id
            )
        )

        # 确保目标目录存在
        target_attachments_dir.mkdir(parents=True, exist_ok=True)

        attachment_metadata = []
        errors = []

        for container_path in attachments:
            filename = Path(container_path).name
            target_file = target_attachments_dir / filename

            # 先尝试将容器内路径转换为宿主机路径
            host_path = self._resolve_container_path_to_host(container_path, task_id)

            if host_path and Path(host_path).exists():
                # 宿主机路径可以直接访问
                shutil.copy2(Path(host_path), target_file)
                self.logger.info(f"附件已复制（宿主机路径）：{host_path} -> {target_file}")
            else:
                # 宿主机路径不存在，尝试从容器内直接提取
                success, error_msg = await self._extract_file_from_container(
                    container_path, target_file
                )
                if not success:
                    errors.append(f"附件 '{container_path}' 无法访问：{error_msg}")
                    continue

            attachment_metadata.append(
                {
                    "filename": filename,
                    "size": target_file.stat().st_size,
                    "container_path": f"~/current_task/attachments/{filename}",
                }
            )

        return attachment_metadata, errors

    async def _extract_file_from_container(
        self, container_path: str, target_file: Path
    ) -> Tuple[bool, str]:
        """
        通过 docker/podman cp 从容器内提取文件

        Args:
            container_path: 容器内绝对路径（如 /tmp/report.md）
            target_file: 宿主机目标文件路径

        Returns:
            (success, error_msg): 是否成功，失败时的错误信息
        """
        runtime = self.root_agent.runtime
        if not runtime or not runtime.container_manager:
            return False, "容器管理器不可用"

        from ...core.container.container_session import ContainerSession

        cm = runtime.container_manager
        runtime_cmd = ContainerSession._find_runtime_cmd(cm.runtime_type)
        container_name = cm.SHARED_CONTAINER_NAME

        cmd = [
            runtime_cmd, "cp",
            f"{container_name}:{container_path}",
            str(target_file),
        ]

        try:
            result = await asyncio.to_thread(
                subprocess.run, cmd,
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and target_file.exists():
                self.logger.info(
                    f"附件已从容器提取：{container_path} -> {target_file}"
                )
                return True, ""
            else:
                stderr = result.stderr.strip() if result.stderr else "未知错误"
                self.logger.warning(
                    f"容器提取失败：{container_path} (exit={result.returncode}, {stderr})"
                )
                return False, f"容器内文件不存在或无法读取 ({stderr})"
        except subprocess.TimeoutExpired:
            return False, "从容器提取文件超时"
        except Exception as e:
            return False, f"提取失败：{e}"

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

        # 情况 1: ~/current_task/... 展开为绝对路径（必须先于相对路径检查）
        if container_path.startswith("~"):
            rel = container_path.lstrip("~/")
            return str(
                runtime.paths.get_agent_work_files_dir(agent_name, task_id) / rel
            )

        # 情况 2: 相对路径 → 基于当前任务目录
        if not path.is_absolute():
            return str(
                runtime.paths.get_agent_work_files_dir(agent_name, task_id)
                / container_path
            )

        # 情况 3: /data/agents/{username}/... → workspace/agent_files/{username}/...
        if container_path.startswith("/data/agents/"):
            relative = container_path.split("/data/agents/")[1]
            return str(runtime.paths.workspace_dir / "agent_files" / relative)

        # 情况 4: 其他绝对路径（可能是宿主机路径，直接返回）
        return container_path
