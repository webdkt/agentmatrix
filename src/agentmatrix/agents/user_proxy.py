from ..agents.base import BaseAgent
from ..core.message import Email
from typing import Callable, Awaitable, Optional
import datetime
import uuid

# 定义一个回调函数的类型：接收一封邮件，返回 None (异步)
OnMailReceived = Callable[[Email], Awaitable[None]]

class UserProxyAgent(BaseAgent):
    def __init__(self, profile) :
        super().__init__(profile)
        self.on_mail_received = None

        # UserProxyAgent 不需要 docker_manager
        # 跳过 Docker 初始化

    def set_mail_handler(self, on_mail_received: OnMailReceived):
        self.on_mail_received = on_mail_received


    async def process_email(self, email: Email):
        """
        当 Matrix 里的 Agent (如 Planner) 给 User 发信时触发
        """
        # 1. 恢复 session（继承自 BaseAgent 的能力）
        session = await self.session_manager.get_session(email)
        self.current_session = session
        self.current_task_id = session["task_id"]

        # 2. 更新 receiver_session_id（如果尚未设置）
        if email.receiver_session_id is None:
            await self.post_office.update_email_receiver_session(
                email_id=email.id,
                receiver_session_id=session["session_id"],
                receiver_name=self.name
            )
            # 🔑 关键修复：同步更新内存对象，否则 WebSocket 回调拿到的还是 null
            email.receiver_session_id = session["session_id"]

        # 3. 记录日志（保持原有逻辑）
        print(f"[{self.name}] 收到邮件: {email.subject}")
        await self.emit("USER_INTERACTION", f"收到来自 {email.sender} 的消息", payload={
            "type": "MAIL_RECEIVED",
            "mail_id": email.id,
            "sender": email.sender,
            "subject": email.subject,
            "body": email.body,
            "in_reply_to": email.in_reply_to,
            "receiver_session_id": session["session_id"],  # 关键：前端需要知道放到哪个会话
            "task_id": session["task_id"]  # 前端也需要 task_id
        })

        # 4. 触发外部钩子（保持原有逻辑）
        if self.on_mail_received:
            # 把这封信扔给外部程序，至于外部程序是打印还是弹窗，我不关心
            await self.on_mail_received(email)
        else:
            # 默认行为：简单的打印到控制台，防止没有任何反应
            print(f"\n[UserProxy 收到邮件] From: {email.sender}\nSubject: {email.subject}\nBody: {email.body}\n")

    async def speak(self, session_id, task_id, to: str, subject, content: str = None, reply_to_id: str = None, attachments=None):
        """
        [Public API]
        这是给宿主程序调用的方法。
        相当于用户开口说话。

        Args:
            session_id: 会话 ID（必需）
            task_id: 任务 ID（必需）
            to: 收件人
            subject: 邮件主题
            content: 邮件内容
            reply_to_id: 回复的邮件ID（由前端控制）
            attachments: 附件列表 (可选)
        """
        if content is None:
            content = subject
            subject = None

        # 通过 session_id 获取 session（如果不存在则创建）
        try:
            session = await self.session_manager.get_session_by_id(session_id)
        except ValueError:
            # Session 不存在，创建新的
            self.logger.info(f"Session {session_id[:8]} not found, creating new session")
            session = await self.session_manager._create_new_session(session_id, self.name, task_id)
            self.session_manager.sessions[session_id] = session
            await self.session_manager._save_session_to_disk(session)

        if not subject:
            self.logger.info(f"🤖 Auto-generating subject for content: {content[:50]}...")
            resp = await self.cerebellum.think(f"""
            请你根据以下邮件内容生成一个高度扼要的邮件主题。明了的说明事情本质就行，不需要具体细节内容，例如"一个问题"，"下载任务" 等等

            [邮件内容]
            {content}

            [输出要求]
            你可以尽量简短的说明思路，但输出的最后一行必须是、也只能是邮件主题本身。例如如果邮件主题是ABC，那么最后一行就是ABC。不多不少，不要增加任何标点符号
            """)
            subject = resp['reply'] or ""
            #取subject 最后一行
            subject = subject.split("\n")[-1]
            self.logger.info(f"✅ Generated subject: {subject}")

        # 🔑 修复：只使用前端传递的 reply_to_id，不做任何自动判断
        # 前端说 reply to 谁，就 reply to 谁
        # 前端没有传 reply_to_id，就是新邮件（in_reply_to = None）
        in_reply_to = reply_to_id  # 可能是 None，也可能是一个邮件 ID

        if in_reply_to:
            self.logger.info(f"📧 Reply to email: {in_reply_to}")
        else:
            self.logger.info(f"📧 New email (no reply_to_id)")

        # 处理附件 metadata
        metadata = {}
        if attachments:
            metadata['attachments'] = attachments
            self.logger.info(f"📎 Email includes {len(attachments)} attachment(s)")

        email = Email(
            sender=self.name,
            recipient=to,
            subject=subject,
            body=content,
            in_reply_to=in_reply_to,  # 🔑 只使用前端传递的值
            task_id=session["task_id"],
            sender_session_id=session["session_id"],  # 关键：设置发件人的 session
            receiver_session_id=None,  # 收件人的 session（由收件人收到后更新）
            metadata=metadata
        )
        await self.post_office.dispatch(email)

        # 更新 reply_mapping
        await self.session_manager.update_reply_mapping(
            msg_id=email.id,
            session_id=session["session_id"],
            task_id=session["task_id"]
        )



