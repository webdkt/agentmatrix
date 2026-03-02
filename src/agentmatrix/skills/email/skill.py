"""
Email Skill - 邮件相关 Actions

提供邮件发送功能：
- send_email: 发送邮件给同事

未来可以扩展：
- check_email: 检查邮件
- read_email: 读取邮件详情
"""

from typing import Any
from ...core.action import register_action


class EmailSkillMixin:
    """
    Email Actions

    提供邮件发送功能（未来可扩展邮件检查、读取等功能）
    """

    @register_action(
        "发邮件给同事，这是和其他人沟通的唯一方式",
        param_infos={
            "to": "收件人 (e.g. 'User')",
            "body": "邮件内容",
            "subject": "邮件主题 (可选，如果不填，系统会自动截取 body 的前20个字)"
        }
    )
    async def send_email(self, to, body, subject=None):
        """
        发送邮件给同事

        Args:
            to: 收件人名称
            body: 邮件内容
            subject: 邮件主题（可选）

        邮件路由逻辑：
        - 如果发给 session 的 original_sender：in_reply_to = session.session_id
        - 如果发给 last_email.sender：in_reply_to = last_email.id
        - 否则：in_reply_to = session.session_id
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

        # 构造邮件
        msg = Email(
            sender=self.root_agent.name,  # 发送者是 BaseAgent
            recipient=to,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
            user_session_id=session["user_session_id"]
        )

        # 发送邮件（通过 root_agent 的 post_office）
        await self.root_agent.post_office.dispatch(msg)

        # 更新 reply_mapping（自动保存到磁盘，通过 root_agent 的 session_manager）
        await self.root_agent.session_manager.update_reply_mapping(
            msg_id=msg.id,
            session_id=session["session_id"],  # 使用已获取的 session 变量
            user_session_id=session["user_session_id"]
        )
