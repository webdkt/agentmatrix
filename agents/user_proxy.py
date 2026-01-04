from agents.base import BaseAgent
from core.message import Email
from typing import Callable, Awaitable, Optional
import datetime
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
        if content is None:
            content = subject
            subject = None

        if not subject:
            resp = await self.cerebellum.think(f"""
            请你根据以下邮件内容生成一个高度扼要的邮件主题。明了的说明事情本质就行，不需要具体细节内容，例如“一个问题”，“下载任务” 等等

            [邮件内容]
            {content}

            [输出要求]
            你可以尽量简短的说明思路，但输出的最后一行必须是、也只能是邮件主题本身。例如如果邮件主题是ABC，那么最后一行就是ABC。不多不少，不要增加任何标点符号
            """)
            subject = resp['reply'] or ""
            #取subject 最后一行
            subject = subject.split("\n")[-1]
        #给subject 后面加上日期yyyy-mm-dd 
        
        subject = subject + " " + datetime.datetime.now().strftime("%Y-%m-%d")
        subject = subject.strip()


        email = Email(
            sender=self.name,
            recipient=to,
            subject=subject,
            body=content,
            in_reply_to=reply_to_id,
            user_session_id=user_session_id
        )
        await self.post_office.dispatch(email)


