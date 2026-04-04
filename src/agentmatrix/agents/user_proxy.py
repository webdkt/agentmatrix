from ..agents.base import BaseAgent
from ..core.message import Email
from ..core.readable_id_generator import generate_readable_id
from typing import Callable, Awaitable, Optional
import asyncio
import datetime
import uuid
import shutil
from pathlib import Path

# 定义一个回调函数的类型：接收一封邮件，返回 None (异步)
OnMailReceived = Callable[[Email], Awaitable[None]]


class UserProxyAgent(BaseAgent):
    def __init__(self, profile, profile_path: str = None):
        super().__init__(profile, profile_path=profile_path)
        self.on_mail_received = None

        # UserProxyAgent 不需要 container_session
        # 跳过 Container Session 初始化

    def set_mail_handler(self, on_mail_received: OnMailReceived):
        self.on_mail_received = on_mail_received

    async def _rename_task_and_session_directories(
        self,
        old_task_id: str,
        old_session_id: str,
        new_task_id: str,
        new_session_id: str,
    ):
        """
        重命名或创建 task 和 session 目录

        如果旧目录存在，移动到新位置
        如果旧目录不存在，创建新目录

        Args:
            old_task_id: 旧的 task_id
            old_session_id: 旧的 session_id
            new_task_id: 新的 task_id
            new_session_id: 新的 session_id
        """
        try:
            # 1. 获取目录路径
            old_work_dir = self.runtime.paths.get_agent_work_files_dir(
                self.name, old_task_id
            )
            old_session_dir = self.runtime.paths.get_agent_session_dir(
                self.name, old_session_id
            )
            new_work_dir = self.runtime.paths.get_agent_work_files_dir(
                self.name, new_task_id
            )
            new_session_dir = self.runtime.paths.get_agent_session_dir(
                self.name, new_session_id
            )

            # 2. 处理 work_files 目录
            if old_work_dir.exists() and old_work_dir != new_work_dir:
                # 旧目录存在：移动
                shutil.move(str(old_work_dir), str(new_work_dir))
                self.logger.info(
                    f"✅ Moved work_files: {old_task_id[:8]} → {new_task_id}"
                )
            elif not new_work_dir.exists():
                # 旧目录不存在：创建新目录
                new_work_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"✅ Created work_files: {new_task_id}")

            # 3. 处理 session 目录
            if old_session_dir.exists() and old_session_dir != new_session_dir:
                # 旧目录存在：移动
                shutil.move(str(old_session_dir), str(new_session_dir))
                self.logger.info(
                    f"✅ Moved session: {old_session_id[:8]} → {new_session_id}"
                )
            elif not new_session_dir.exists():
                # 旧目录不存在：创建新目录
                new_session_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"✅ Created session: {new_session_id}")

        except Exception as e:
            self.logger.error(
                f"❌ Failed to rename/create directories: {e}", exc_info=True
            )
            # 不抛出异常，继续执行（目录操作失败不应该阻塞邮件发送）

    async def _route_email(self, email: Email):
        """
        轻量级路由：session 归属 → 更新 recipient_session_id → 推送前台。
        不创建 MicroAgent，不做 AI 处理。
        """
        session = await self.session_manager.get_session(email)
        self.current_session = session
        self.current_task_id = session["task_id"]

        # 更新 recipient_session_id
        if email.recipient_session_id is None:
            await self.post_office.update_email_receiver_session(
                email_id=email.id,
                recipient_session_id=session["session_id"],
                receiver_name=self.name,
            )
            email.recipient_session_id = session["session_id"]

        # 维护 user_sessions（用户收件：is_read=0，对方是发件人）
        self.post_office.email_db.upsert_user_session(
            email=email,
            user_session_id=session["session_id"],
            agent_name=email.sender,
            is_read=0,
        )

        # 触发外部钩子（同时负责前台推送，避免重复通知）
        if self.on_mail_received:
            await self.on_mail_received(email)

        # 标记邮件已处理（从 email_to_process 移到 emails 归档表）
        self.post_office.email_db.mark_emails_processed([email.id])

    async def _main_loop(self):
        """简化版 main loop：只收邮件、路由，无 session 生命周期管理。"""
        self.logger.info("🔄 UserProxyAgent Main loop 已启动")
        try:
            while True:
                email = await self.inbox.get()
                try:
                    self.last_received_email = email
                    await self._route_email(email)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.exception(f"Error routing email in {self.name}")
                finally:
                    self.inbox.task_done()
        except asyncio.CancelledError:
            self.logger.info("🔄 UserProxyAgent Main loop 已停止")
            raise

    async def speak(
        self,
        session_id,
        task_id,
        to: str,
        subject,
        content: str = None,
        reply_to_id: str = None,
        attachments=None,
    ):
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
            self.logger.info(
                f"Session {session_id[:8]} not found, creating new session"
            )
            session = await self.session_manager._create_new_session(
                session_id, self.name, task_id
            )
            self.session_manager.sessions[session_id] = session
            # 🆕 不保存空session，避免后续移动目录时的冗余操作

        if not subject:
            self.logger.info(
                f"🤖 Auto-generating subject for content: {content[:50]}..."
            )
            resp = await self.cerebellum.think(f"""
            请你根据以下邮件内容生成一个高度扼要的邮件主题。明了的说明事情本质就行，不需要具体细节内容，例如"一个问题"，"下载任务" 等等

            [邮件内容]
            {content}

            [输出要求]
            你可以尽量简短的说明思路，但输出的最后一行必须是、也只能是邮件主题本身。例如如果邮件主题是ABC，那么最后一行就是ABC。不多不少，不要增加任何标点符号
            """)
            subject = resp["reply"] or ""
            # 取subject 最后一行
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
            # 🆕 新邮件：生成 readable ID 并重命名目录
            # 1. 生成 readable ID
            readable_id = generate_readable_id(subject)
            self.logger.info(f"🏷️ Generated readable ID: {readable_id}")

            # 2. 保存旧的 ID（用于重命名目录）
            old_task_id = task_id
            old_session_id = session_id

            # 3. 替换为新的 readable ID
            new_task_id = readable_id
            new_session_id = readable_id

            # 4. 重命名目录
            await self._rename_task_and_session_directories(
                old_task_id, old_session_id, new_task_id, new_session_id
            )

            # 5. 更新 session 字典中的 ID
            session["session_id"] = new_session_id
            session["task_id"] = new_task_id

            # 6. 从旧 ID 移除，添加到新 ID
            del self.session_manager.sessions[old_session_id]
            self.session_manager.sessions[new_session_id] = session

            # 7. 重新保存 session（使用新 ID）
            await self.session_manager._save_session_to_disk(session)

            # 8. 更新局部变量
            session_id = new_session_id
            task_id = new_task_id

            self.logger.info(
                f"✅ Session ID updated: {old_session_id[:8]} → {new_session_id}"
            )

        # 处理附件 metadata
        metadata = {}
        if attachments:
            metadata["attachments"] = attachments
            self.logger.info(f"📎 Email includes {len(attachments)} attachment(s)")

        email = Email(
            sender=self.name,
            recipient=to,
            subject=subject,
            body=content,
            in_reply_to=in_reply_to,  # 🔑 只使用前端传递的值
            task_id=session["task_id"],
            sender_session_id=session["session_id"],  # 关键：设置发件人的 session
            recipient_session_id=None,  # 收件人的 session（由收件人收到后更新）
            metadata=metadata,
        )
        await self.post_office.dispatch(email)

        # 维护 user_sessions（用户发件：is_read=1，对方是收件人）
        self.post_office.email_db.upsert_user_session(
            email=email, user_session_id=session["session_id"], agent_name=to, is_read=1
        )

        # 更新 reply_mapping
        await self.session_manager.update_reply_mapping(
            msg_id=email.id,
            session_id=session["session_id"],
            task_id=session["task_id"],
        )

        return email
