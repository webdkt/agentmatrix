"""
Email Proxy Service - 邮件代理服务

职责：
1. 从IMAP服务器接收外部邮件
2. 将外部邮件转换为内部Email格式
3. 将内部Email发送到SMTP服务器
4. 通过subject标记管理session
5. 只处理来自User邮箱的邮件
"""

import imaplib
import smtplib
import email
import re
import os
import asyncio
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from ..core.id_generator import IDGenerator
from ..core.message import Email
from ..core.log_util import AutoLoggerMixin
from ..db.agent_matrix_db import AgentMatrixDB


class EmailProxyService(AutoLoggerMixin):
    """
    Email Proxy Service

    连接外部邮箱和AgentMatrix的桥梁服务：
    - 从IMAP拉取邮件
    - 转换为内部Email
    - 发送到PostOffice
    - 从内部Email发送到SMTP
    """

    def __init__(self, paths: 'MatrixPaths', config: dict, post_office, db_path: str, parent_logger=None):
        """
        初始化EmailProxy服务

        Args:
            paths: MatrixPaths 对象
            config: Email Proxy配置
            post_office: PostOffice实例
            db_path: 数据库路径
            parent_logger: 父logger（可选）
        """
        self.paths = paths
        self.config = config
        self.post_office = post_office

        # 设置logger
        if parent_logger:
            self._parent_logger = parent_logger

        # 邮箱配置
        self.matrix_mailbox = config['matrix_mailbox']
        self.user_mailbox = config['user_mailbox']

        # IMAP/SMTP配置
        self.imap_config = config['imap']
        self.smtp_config = config['smtp']

        # 数据库
        self.db = AgentMatrixDB(db_path)

        # 运行状态
        self._running = False
        self._fetch_task = None

        self.logger.info(f"📧 EmailProxy初始化完成 (Matrix: {self.matrix_mailbox}, User: {self.user_mailbox})")

    async def start(self):
        """启动EmailProxy服务"""
        self._running = True
        self._fetch_task = asyncio.create_task(self._fetch_loop())
        self.logger.info(f"✅ EmailProxy服务已启动")

    async def stop(self):
        """停止EmailProxy服务"""
        self._running = False
        if self._fetch_task:
            self._fetch_task.cancel()
            try:
                await self._fetch_task
            except asyncio.CancelledError:
                pass
        # 关闭数据库连接
        if hasattr(self.db, 'conn') and self.db.conn:
            self.db.conn.close()
            self.logger.info("EmailProxy DB connection closed.")
        self.logger.info("🛑 EmailProxy服务已停止")

    async def _fetch_loop(self):
        """定期拉取外部邮件"""
        while self._running:
            try:
                await self.fetch_external_emails()
            except Exception as e:
                self.logger.error(f"拉取邮件失败: {e}", exc_info=True)

            # 每30秒拉取一次
            await asyncio.sleep(30)

    async def fetch_external_emails(self):
        """
        从IMAP服务器拉取新邮件

        流程：
        1. 连接IMAP服务器
        2. 获取未读邮件
        3. 过滤来自User邮箱的邮件
        4. 转换为内部Email
        5. 发送到PostOffice
        """
        try:
            # 连接IMAP
            imap = imaplib.IMAP4_SSL(
                self.imap_config['host'],
                self.imap_config['port']
            )
            imap.login(self.imap_config['user'], self.imap_config['password'])
            imap.select('INBOX')

            # 获取未读邮件
            status, messages = imap.search(None, '(UNSEEN)')

            if status != 'OK':
                self.logger.warning(f"IMAP搜索失败: {status}")
                imap.logout()
                return

            msg_count = len(messages[0].split()) if messages[0] else 0
            if msg_count > 0:
                self.logger.info(f"📬 发现 {msg_count} 封未读邮件")

            for msg_id in messages[0].split():
                try:
                    _, msg_data = imap.fetch(msg_id, '(RFC822)')
                    raw_email = email.message_from_bytes(msg_data[0][1])

                    # 只处理来自User邮箱的邮件
                    from_addr = self._extract_email_address(raw_email['From'])
                    if from_addr != self.user_mailbox:
                        self.logger.info(f"⏭️  忽略非User邮箱邮件: {from_addr}")
                        continue

                    # 转换为内部Email
                    internal_email = self.convert_to_internal(raw_email)

                    # 发送到PostOffice
                    await self.post_office.dispatch(internal_email)

                    self.logger.info(f"✅ 转发邮件: {raw_email['From']} → {internal_email.recipient}")

                except Exception as e:
                    self.logger.error(f"处理邮件失败: {e}", exc_info=True)

            imap.close()
            imap.logout()

        except imaplib.IMAP4.error as e:
            self.logger.error(f"IMAP连接错误: {e}")
        except Exception as e:
            self.logger.error(f"拉取邮件异常: {e}", exc_info=True)

    def convert_to_internal(self, raw_email) -> Email:
        """
        真实邮件 → 内部Email

        转换逻辑：
        1. 解析headers
        2. 从subject提取session_id
        3. 清理subject（移除标记）
        4. 解析收件人（@mention或默认）
        5. 确定sender
        6. 解析body
        7. 构造Email

        Args:
            raw_email: 原始邮件对象

        Returns:
            内部Email对象
        """
        # 1. 解析headers
        subject = self._decode_header(raw_email['Subject'])
        from_addr = self._extract_email_address(raw_email['From'])

        # 2. 从subject提取session_id
        session_id = IDGenerator.extract_session_id(subject)

        # 3. 清理subject（移除标记）
        clean_subject = IDGenerator.remove_session_tag(subject)

        # 4. 解析收件人（@mention或默认）
        recipient = self._parse_recipient(clean_subject, raw_email)

        # 5. 确定sender（user_mailbox映射为User）
        sender = "User"


        # 7. 生成内部email_id
        email_id = IDGenerator.generate_email_id()

        # 8. 生成task_id
        if session_id:
            # 找到session，用session_id作为task_id
            task_id = session_id
        else:
            # 新session，生成新的session_id和task_id
            session_id = IDGenerator.generate_session_id()
            task_id = session_id

        # 9. 构造Email
        return Email(
            id=email_id,
            sender=sender,
            recipient=recipient,
            subject=clean_subject,
            body=body,
            in_reply_to=None,  # 不需要，用subject即可
            task_id=task_id,
            sender_session_id=session_id,
            receiver_session_id=None,
            metadata={
                'original_message_id': raw_email['Message-ID'],
                'original_sender': from_addr,
                'original_subject': subject,  # 保存原始subject（带标记）
                'is_external': True,
                'attachments': attachments
            }
        )

    def _parse_recipient(self, subject: str, raw_email) -> str:
        """
        从邮件中解析收件人Agent

        优先级：
        1. Subject中的@mention
        2. Body第一行的@mention
        3. 默认User

        Args:
            subject: 清理后的subject
            raw_email: 原始邮件对象

        Returns:
            收件人Agent名称
        """
        # 1. 检查subject中的@mention
        match = re.search(r'@(\w+)', subject)
        if match:
            agent_name = match.group(1).capitalize()
            self.logger.debug(f"🎯 从subject解析收件人: {agent_name}")
            return agent_name

        # 2. 检查body第一行
        body = self._extract_body(raw_email)
        if body:
            first_line = body.strip().split('\n')[0]
            if first_line.startswith('@'):
                agent_name = first_line[1:].split()[0].capitalize()
                self.logger.debug(f"🎯 从body解析收件人: {agent_name}")
                return agent_name

        # 3. 默认发给User
        return 'User'

    async def send_to_external(self, internal_email: Email):
        """
        内部Email → 外部邮件发送

        Args:
            internal_email: 内部Email对象
        """
        # 1. 检查是否需要发送到外部
        if not internal_email.metadata.get('is_external'):
            return

        # 获取原始发送者邮箱
        original_sender = internal_email.metadata.get('original_sender')
        if not original_sender:
            self.logger.warning(f"无法确定外部收件人: {internal_email.id}")
            return

        try:
            # 2. 获取session_id
            session_id = internal_email.metadata.get('sender_session_id', '')

            # 3. 添加session标记到subject
            tagged_subject = IDGenerator.add_session_tag(
                internal_email.subject,
                session_id
            )

            # 4. 生成外部Message-ID
            domain = self.matrix_mailbox.split('@')[1]
            external_message_id = IDGenerator.generate_message_id(domain)

            # 5. 构造邮件
            msg = MIMEMultipart()
            msg['From'] = self.matrix_mailbox
            msg['To'] = original_sender
            msg['Subject'] = tagged_subject
            msg['Message-ID'] = external_message_id

            # 邮件正文
            mime_body = MIMEText(internal_email.body, 'plain', 'utf-8')
            msg.attach(mime_body)

            # 添加附件
            attachments = internal_email.metadata.get('attachments', [])
            if attachments:
                for att in attachments:
                    self._add_attachment_to_email(msg, att, internal_email.sender, internal_email.metadata.get('task_id', ''))

            # 6. 发送邮件
            with smtplib.SMTP(
                self.smtp_config['host'],
                self.smtp_config['port']
            ) as server:
                server.starttls()
                server.login(
                    self.smtp_config['user'],
                    self.smtp_config['password']
                )
                server.send_message(msg)

            self.logger.info(f"📧 发送外部邮件: {internal_email.sender} → {original_sender}")

        except Exception as e:
            self.logger.error(f"发送外部邮件失败: {e}", exc_info=True)

    def _extract_email_address(self, email_header: str) -> str:
        """
        从email header中提取邮箱地址

        处理格式：
        - "Name <email@example.com>"
        - "email@example.com"

        Args:
            email_header: Email header字符串

        Returns:
            邮箱地址
        """
        if not email_header:
            return ""

        # 处理 "Name <email@example.com>" 格式
        match = re.search(r'<(.+?)>', email_header)
        if match:
            return match.group(1)

        return email_header.strip()

    def _decode_header(self, header: str) -> str:
        """
        解码email header

        Args:
            header: Email header字符串

        Returns:
            解码后的字符串
        """
        if not header:
            return ""

        decoded_parts = []
        for content, encoding in decode_header(header):
            if isinstance(content, bytes):
                decoded_parts.append(content.decode(encoding or 'utf-8', errors='ignore'))
            else:
                decoded_parts.append(content)

        return ''.join(decoded_parts)

    def _extract_body_and_attachments(self, raw_email, task_id: str) -> tuple:
        """
        提取邮件正文和附件

        Args:
            raw_email: 原始邮件对象
            task_id: 任务ID（用于确定附件存储路径）

        Returns:
            (邮件正文, 附件metadata列表)
        """
        body = ""
        attachments = []

        try:
            if raw_email.is_multipart():
                for part in raw_email.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition', ''))

                    # 提取正文（text/plain）
                    if content_type == 'text/plain' and 'attachment' not in content_disposition:
                        charset = part.get_content_charset() or 'utf-8'
                        body = part.get_payload(decode=True).decode(charset, errors='ignore')

                    # 提取附件
                    elif 'attachment' in content_disposition:
                        attachment_metadata = self._process_attachment(part, task_id)
                        if attachment_metadata:
                            attachments.append(attachment_metadata)
            else:
                # 非multipart邮件
                charset = raw_email.get_content_charset() or 'utf-8'
                body = raw_email.get_payload(decode=True).decode(charset, errors='ignore')

        except Exception as e:
            self.logger.warning(f"提取邮件正文和附件失败: {e}")

        return body, attachments

    def _process_attachment(self, part, task_id: str) -> Optional[dict]:
        """
        处理单个附件

        下载附件到User的attachments目录

        Args:
            part: 邮件的attachment part
            task_id: 任务ID

        Returns:
            附件metadata，如果处理失败返回None
        """
        try:
            # 获取附件文件名
            filename = part.get_filename()
            if not filename:
                return None

            # 解码文件名（可能是RFC 2047编码）
            from email.header import decode_header
            decoded_parts = decode_header(filename)
            filename = ''
            for content, encoding in decoded_parts:
                if isinstance(content, bytes):
                    filename += content.decode(encoding or 'utf-8', errors='ignore')
                else:
                    filename += content

            # 确定保存路径
            user_attachments_dir = self.paths.get_agent_attachments_dir("User", task_id)
            user_attachments_dir.mkdir(parents=True, exist_ok=True)

            # 保存附件
            file_path = user_attachments_dir / filename
            with open(file_path, 'wb') as f:
                f.write(part.get_payload(decode=True))

            # 获取文件大小
            file_size = file_path.stat().st_size

            self.logger.info(f"✅ 附件已保存: {filename} ({file_size} bytes)")

            # 返回metadata
            return {
                'filename': filename,
                'size': file_size,
                'container_path': f'/work_files/attachments/{filename}'
            }

        except Exception as e:
            self.logger.error(f"处理附件失败: {e}")
            return None

    def _add_attachment_to_email(self, msg: MIMEMultipart, attachment: dict, sender: str, task_id: str):
        """
        添加附件到邮件

        Args:
            msg: MIME邮件对象
            attachment: 附件metadata
            task_id: 任务ID
        """
        try:
            from email.mime.application import MIMEApplication
            from email.encoders import encode_base64

            filename = attachment.get('filename')
            container_path = attachment.get('container_path', '')

            # 解析附件路径
            # container_path格式: /work_files/attachments/report.pdf
            # 宿主机路径: {workspace_root}/agent_files/{agent_name}/work_files/{task_id}/attachments/{filename}
            
            # 从container_path提取filename（如果没有从metadata获取）
            if not filename:
                filename = container_path.split('/')[-1]
            
            if not filename:
                self.logger.warning("附件文件名为空，跳过")
                return

            # 构造宿主机路径
            # 假设附件来自发送者agent
            sender = msg['From']  # 这里的From是matrix_mailbox，不是发送agent
            # 需要从Email的sender字段获取
            # 但在这个上下文中，我们没有sender信息
            # 让我们使用task_id来定位附件
            
            # 附件应该在发送者的attachments目录中
            # 由于我们在send_to_external中没有发送者信息，我们需要从其他地方获取
            # 使用实际的发送者
            agent_name = sender
            
            file_path = self.paths.get_agent_attachments_dir(agent_name, task_id) / filename
            
            if not file_path.exists():
                self.logger.warning(f"附件文件不存在: {file_path}")
                return
            
            # 读取文件
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # 创建MIME附件
            part = MIMEApplication(file_data)
            part.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(part)
            
            self.logger.info(f"✅ 添加附件: {filename} ({len(file_data)} bytes)")
            
        except Exception as e:
            self.logger.error(f"添加附件失败: {e}", exc_info=True)
