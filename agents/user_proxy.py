from agents.base import BaseAgent
from core.message import Email
from typing import Callable, Awaitable, Optional

import uuid

# 定义一个回调函数的类型：接收一封邮件，返回 None (异步)
OnMailReceived = Callable[[Email], Awaitable[None]]

class UserProxyAgent(BaseAgent):
    def __init__(self, profile) :
        super().__init__(profile)
        self.on_mail_received = None
        
    
    def set_mail_handler(self, on_mail_received: OnMailReceived):
        self.on_mail_received = on_mail_received


    async def process_email(self, email: Email):
        """
        当 Matrix 里的 Agent (如 Planner) 给 User 发信时触发
        """
        print(f"[{self.name}] 收到邮件: {email.subject}")
        # 1. 记录日志 (BaseAgent 能力)
        await self.emit("USER_INTERACTION", f"收到来自 {email.sender} 的消息", payload={
            "type": "MAIL_RECEIVED",
            "mail_id": email.id,
            "sender": email.sender,
            "subject": email.subject,
            "body": email.body,
            "in_reply_to": email.in_reply_to
        })

        # 2. 触发外部钩子 (如果定义了的话)
        if self.on_mail_received:
            # 把这封信扔给外部程序，至于外部程序是打印还是弹窗，我不关心
            await self.on_mail_received(email)
        else:
            # 默认行为：简单的打印到控制台，防止没有任何反应
            print(f"\n[UserProxy 收到邮件] From: {email.sender}\nSubject: {email.subject}\nBody: {email.body}\n")

    async def speak(self, user_session_id, to: str, subject, content: str =None, reply_to_id: str = None):
        """
        [Public API]
        这是给宿主程序调用的方法。
        相当于用户开口说话。
        """


        email = Email(
            sender=self.name,
            recipient=to,
            subject=subject,
            body=content,
            in_reply_to=reply_to_id,
            user_session_id=user_session_id
        )
        await self.post_office.dispatch(email)


