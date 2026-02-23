"""
Base Skill - 所有 BaseAgent 必备的基础 Actions

包含 4 个基础 actions：
- send_email: 发送邮件给同事
- rest_n_wait: 简单休息
- take_a_break: 60秒休息
- get_current_datetime: 获取当前时间

注意：all_finished 不在此 skill 中，它硬编码在 MicroAgent 中。
"""

import asyncio
from typing import Any
from ...core.action import register_action


class BaseSkillMixin:
    """
    Base Agent 必备的基础 Actions

    提供 BaseAgent 必需的核心功能，如发送邮件、获取时间等。
    """

    @register_action(
        "检查当前日期和时间，你不知道日期和时间，如果需要日期时间信息必须调用此action",
        param_infos={}
    )
    async def get_current_datetime(self):
        """获取当前日期和时间"""
        from datetime import datetime
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")

    @register_action(
        "休息一下，工作做完了，或者需要等待回信才能继续",
        param_infos={}
    )
    async def rest_n_wait(self):
        """简单休息（no-op，用于暂停工作）"""
        # 什么都不做，直接返回
        pass

    @register_action(
        "Take a break，让身体恢复一下",
        param_infos={}
    )
    async def take_a_break(self):
        """扩展休息（60秒 sleep）"""
        await asyncio.sleep(60)
        return "Return from Break"

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
