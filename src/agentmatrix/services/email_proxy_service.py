"""
Email Proxy Service - 邮件代理服务

职责：
1. 从IMAP服务器接收外部邮件（IDLE实时推送 + 轮询降级）
2. 解析Subject中的session标记并调用UserProxyAgent.speak()
3. 监听PostOffice，当Agent发邮件给User时发送到外部邮箱
4. 通过subject标记管理session_id和task_id的映射

Subject格式：
- Agent → User: 原始主题 #{agent_name}#{task_id}#{user_session_id}#{agent_session_id}#
- User → Agent (新会话): @{agent_name} 主题内容
- User → Agent (回复): 原始主题 #{agent_name}#{task_id}#{user_session_id}#{agent_session_id}#
"""

import smtplib
import email
import re
import os
import asyncio
import imaplib
from email.header import decode_header
from email import message_from_bytes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Optional
from imap_tools import MailBox
from imap_tools.utils import check_command_status
from imap_tools.errors import MailboxLoginError

from ..core.id_generator import IDGenerator
from ..core.message import Email
from ..core.log_util import AutoLoggerMixin
from ..db.agent_matrix_db import AgentMatrixDB


class EmailProxyService(AutoLoggerMixin):
    """
    Email Proxy Service

    连接外部邮箱和AgentMatrix的桥梁服务：
    - 从IMAP拉取邮件并调用UserProxyAgent.speak()
    - 监听PostOffice的dispatch事件，发送外部邮件
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
        self.user_agent_name = post_office.user_agent_name

        # 设置logger
        if parent_logger:
            self._parent_logger = parent_logger

        # 邮箱配置
        self.matrix_mailbox = config['matrix_mailbox']
        self.user_mailbox = config['user_mailbox']
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

        # 1. 注册PostOffice hook
        self.post_office.on_email_sent.append(self._on_email_sent_handler)

        # 2. 启动IMAP轮询
        self._fetch_task = asyncio.create_task(self._fetch_loop())

        self.logger.info("✅ Email Proxy服务已启动")

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

        self.logger.info("🛑 Email Proxy服务已停止")

    async def _fetch_loop(self):
        """使用 IMAP IDLE 实时推送模式"""
        while self._running:
            try:
                await self._idle_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"IDLE 循环失败: {e}", exc_info=True)
                # 发生错误时等待 5 秒后重试
                if self._running:
                    try:
                        await asyncio.sleep(5)
                    except asyncio.CancelledError:
                        break

    async def fetch_external_emails(self, mailbox=None):
        """
        从IMAP服务器拉取新邮件

        Args:
            mailbox: 可选的现有 MailBox 对象（用于 IDLE 模式）
        """
        loop = asyncio.get_event_loop()
        raw_emails = await loop.run_in_executor(
            None,
            lambda: self._fetch_emails_sync(mailbox)
        )

        for raw_email in raw_emails:
            await self.process_external_email(raw_email)

    def _fetch_emails_sync(self, mailbox=None):
        """
        同步方法：从IMAP拉取邮件（使用 imap_tools）

        Args:
            mailbox: 可选的现有 MailBox 对象（用于 IDLE 模式）
                     如果为 None，则创建新连接并在完成后关闭

        Returns:
            list: 原始邮件对象列表 (email.message.Message)
        """
        close_connection = (mailbox is None)
        if mailbox is None:
            mailbox = self._create_imap_connection()

        emails = []
        try:
            # 搜索未读邮件
            for msg in mailbox.fetch('(UNSEEN)'):
                # 转换为 email.message.Message 对象
                raw_email = message_from_bytes(msg.obj.as_bytes())
                emails.append(raw_email)

            return emails

        finally:
            if close_connection and mailbox:
                mailbox.logout()

    def _send_id_command(self, client):
        """
        发送 IMAP ID 命令（国内邮箱如163.com/qq.com/sina.com必需）

        163.com 等邮箱在 IDLE 前必须收到 ID 命令，否则会静默断开或不推送新邮件。
        ID 命令格式遵循 RFC 2971: ID ("key1" "value1" "key2" "value2" ...)
        """
        try:
            # 注册 ID 命令到 imaplib（imaplib 默认不包含此命令）
            if "ID" not in imaplib.Commands:
                imaplib.Commands["ID"] = "NONAUTH"

            # 构造 ID 参数，使用 RFC 2971 标准格式
            # 参数列表：field_list = "(" string *(SP string) ")"
            # 每对是一个 (key, value)，值可以为 NIL
            id_fields = (
                '"name" "AgentMatrix"'
                ' "contact" "agentmatrix@163.com"'
                ' "version" "1.0.0"'
                ' "vendor" "AgentMatrix"'
            )
            id_arg = f'({id_fields})'

            tag = client._command("ID", id_arg)
            resp = client._get_response()
            self.logger.debug(f"📋 ID 命令响应: {resp}")
        except Exception as e:
            self.logger.info(f"📋 ID 命令不被支持或失败（可忽略）: {e}")

    def _create_imap_connection(self):
        """
        创建并认证 IMAP 连接

        顺序：CONNECT → LOGIN → ID → SELECT INBOX

        注意：不能用 imap_tools 的 MailBox.login()，因为它在内部会直接 SELECT INBOX，
        而国内邮箱（163.com 等）要求先发 ID 命令才能 SELECT，否则报 "Unsafe Login"。
        所以这里手动执行 LOGIN，然后发 ID，最后 SELECT INBOX。
        """
        mailbox = MailBox(self.imap_config['host'])

        # 1. LOGIN（不自动 SELECT INBOX）
        login_result = mailbox.client._simple_command(
            'LOGIN', self.imap_config['user'], mailbox.client._quote(self.imap_config['password'])
        )
        check_command_status(login_result, MailboxLoginError)
        mailbox.client.state = 'AUTH'

        # 2. 发送 ID 命令（必须在 SELECT 之前）
        self._send_id_command(mailbox.client)

        # 3. SELECT INBOX
        mailbox.folder.set('INBOX')
        mailbox.login_result = login_result

        return mailbox

    # IDLE 超时秒数。RFC 2177 建议不超过 29 分钟。
    # 163.com 实测会在 2~5 分钟无响应时静默断开，所以用 120 秒作为 poll 超时，
    # 每次 poll 返回后重新进入 IDLE（start→poll→stop 循环），相当于 keep-alive。
    _IDLE_POLL_TIMEOUT = 120

    async def _idle_loop(self):
        """
        IMAP 收信循环：IDLE 实时推送 + 自动重连 + 轮询降级

        关键设计：
        1. 每次 IDLE 用较短超时（120s），poll 返回后 stop→start 重新进入 IDLE，
           相当于 keep-alive，避免 163.com 等服务器超时断开。
        2. 如果服务器明确不支持 IDLE（BAD command not support），立即降级到轮询。
        3. 网络等临时错误则重连后继续尝试 IDLE，重连 N 次仍失败才降级。
        """
        loop = asyncio.get_event_loop()
        max_idle_failures = 3
        idle_failures = 0

        while self._running:
            mailbox = None
            try:
                # 1. 创建连接
                self.logger.info("🔗 连接到 IMAP 服务器...")
                mailbox = await loop.run_in_executor(None, self._create_imap_connection)
                self.logger.info("✅ IMAP 连接成功")
                idle_failures = 0  # 连接成功，重置失败计数

                # 2. 启动时先拉取一次现有未读邮件
                self.logger.info("🔍 启动时拉取现有未读邮件...")
                await self.fetch_external_emails(mailbox)
                self.logger.info("✅ 启动拉取完成")

                # 3. 检查服务器是否支持 IDLE
                caps = mailbox.client.capabilities
                if b'IDLE' not in caps:
                    self.logger.warning(f"⚠️ 服务器不支持 IDLE（CAPS: {caps[:10]}...），直接进入轮询模式")
                    mailbox.logout()
                    mailbox = None
                    await self._polling_loop()
                    break

                # 4. 进入 IDLE 循环
                await self._run_idle(mailbox, loop)

            except asyncio.CancelledError:
                break
            except Exception as e:
                err_msg = str(e)
                # 服务器明确不支持 IDLE 命令（如 163.com）→ 直接降级到轮询
                if 'BAD' in err_msg and 'command not support' in err_msg.lower():
                    self.logger.warning(f"⚠️ 服务器不支持 IDLE 命令，降级到轮询模式")
                    await self._polling_loop()
                    break

                idle_failures += 1
                self.logger.error(f"IMAP 连接/IDLE 失败 ({idle_failures}/{max_idle_failures}): {e}",
                                  exc_info=(idle_failures <= 1))
                if idle_failures >= max_idle_failures:
                    self.logger.warning("⚠️ IDLE 连续失败，降级到轮询模式（每 2 分钟）")
                    await self._polling_loop()
                    break
                # 等待后重连
                if self._running:
                    await asyncio.sleep(5)

            finally:
                if mailbox:
                    try:
                        mailbox.logout()
                    except Exception:
                        pass
                    mailbox = None

        self.logger.info("🛑 IMAP 收信循环已停止")

    async def _run_idle(self, mailbox, loop):
        """
        在已连接的 mailbox 上运行 IDLE 循环。

        使用 start → poll → stop 的三步模式（而非 wait），
        每次 poll 短超时后重新 start，起到 keep-alive 作用。
        """
        while self._running:
            # 启动 IDLE
            await loop.run_in_executor(None, mailbox.idle.start)
            self.logger.debug("📡 IDLE 已启动，等待推送...")

            try:
                # 短超时 poll，避免服务器断开
                responses = await loop.run_in_executor(
                    None, lambda: mailbox.idle.poll(timeout=self._IDLE_POLL_TIMEOUT)
                )
            finally:
                # 无论 poll 结果如何，都 stop IDLE（恢复普通命令模式）
                try:
                    await loop.run_in_executor(None, mailbox.idle.stop)
                except Exception:
                    pass  # stop 失败通常意味着连接已断开

            if responses:
                self.logger.info(f"📬 收到 IDLE 推送: {len(responses)} 条响应")
                await self.fetch_external_emails(mailbox)
            else:
                self.logger.debug("💓 IDLE 超时，重新进入 IDLE")

    async def _polling_loop(self):
        """
        轮询模式（降级方案）：每 2 分钟检查一次新邮件

        IDLE 连续失败后进入此模式，每 2 分钟创建新连接拉取邮件。
        """
        self.logger.info("⏰ 进入轮询模式，每 2 分钟检查一次新邮件")

        while self._running:
            try:
                # 可中断的 sleep
                for _ in range(120):  # 120 秒 = 2 分钟
                    if not self._running:
                        return
                    await asyncio.sleep(1)

                if not self._running:
                    return

                # 拉取新邮件（每次创建新连接）
                self.logger.info("🔍 检查新邮件...")
                await self.fetch_external_emails(None)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"轮询失败: {e}", exc_info=True)
                break

    def _parse_ask_user_metadata(self, subject: str) -> Optional[dict]:
        """
        解析 subject 中的 ask_user 标记

        标记格式：#ASK_USER#{agent_name}#{agent_session_id}#

        Args:
            subject: 邮件 subject（可能包含标记）

        Returns:
            如果是 ask_user 回复，返回 dict：
                {
                    'agent_name': str,
                    'agent_session_id': str
                }
            否则返回 None
        """
        # 正则表达式匹配 #ASK_USER#...#
        match = re.search(r'#ASK_USER#([^#]+)#([^#]+)#', subject)
        if match:
            agent_name = match.group(1)
            agent_session_id = match.group(2)
            return {
                'agent_name': agent_name,
                'agent_session_id': agent_session_id
            }
        return None

    async def _handle_ask_user_reply(self, internal_email: Email):
        """
        处理 ask_user 回复邮件

        流程：
        1. 从 metadata 获取 ask_user_metadata
        2. 查找对应的 Agent
        3. 调用 Agent 的 submit_user_input() 方法
        4. 捕获异常（RuntimeError）并发送反馈邮件

        Args:
            internal_email: 内部Email对象（metadata 包含 ask_user_metadata）
        """
        try:
            # 1. 获取 ask_user_metadata
            ask_user_metadata = internal_email.metadata.get('ask_user_metadata')
            if not ask_user_metadata:
                self.logger.warning("⚠️ Email 缺少 ask_user_metadata，跳过处理")
                return

            agent_name = ask_user_metadata.get('agent_name')
            agent_session_id = ask_user_metadata.get('agent_session_id')

            self.logger.info(f"📬 检测到 ask_user 回复: agent={agent_name}, session={agent_session_id[:8] if agent_session_id else None}...")

            # 2. 查找 Agent
            agent = self.post_office.directory.get(agent_name)
            if not agent:
                # Agent 不存在
                self.logger.warning(f"⚠️ Agent {agent_name} 不存在")
                await self._send_ask_user_feedback(
                    internal_email,
                    success=False,
                    message=f"未找到 Agent: {agent_name}，可能 Agent 已停止或名称错误"
                )
                return

            # 3. 提取用户回答（邮件正文）
            answer = internal_email.body.strip()
            if not answer:
                self.logger.warning("⚠️ ask_user 回复内容为空")
                await self._send_ask_user_feedback(
                    internal_email,
                    success=False,
                    message="回复内容为空，请输入你的回答"
                )
                return

            # 4. 调用 Agent 的 submit_user_input() 方法
            try:
                await agent.submit_user_input(answer, agent_session_id)
                self.logger.info(f"✅ 成功提交 ask_user 回复给 {agent_name}")

                # 发送成功反馈
                await self._send_ask_user_feedback(
                    internal_email,
                    success=True,
                    message=f"✅ 你的回答已成功提交给 {agent_name}"
                )

            except RuntimeError as e:
                # Agent 当前不在等待状态（已经回答或超时）
                self.logger.warning(f"⚠️ Agent {agent_name} 当前不在等待用户输入状态: {e}")
                await self._send_ask_user_feedback(
                    internal_email,
                    success=False,
                    message=f"提交失败：{agent_name} 当前不在等待状态，可能已经回答或任务已结束"
                )

        except Exception as e:
            self.logger.error(f"❌ 处理 ask_user 回复失败: {e}", exc_info=True)
            await self._send_ask_user_feedback(
                internal_email,
                success=False,
                message=f"处理失败：{str(e)}"
            )

    async def _send_ask_user_feedback(self, original_email: Email, success: bool, message: str):
        """
        发送 ask_user 反馈邮件

        Args:
            original_email: 原始的 ask_user 回复邮件
            success: 是否成功
            message: 反馈消息
        """
        try:
            # 获取原始发送者邮箱
            original_sender = original_email.metadata.get('original_sender')
            if not original_sender:
                self.logger.warning("⚠️ 无法确定反馈邮件收件人")
                return

            # 构造 subject
            status = "✅" if success else "❌"
            subject = f"{status} ask_user 回复反馈"

            # 构造邮件正文
            body = f"""你好，

{message}

---
原始问题：{original_email.subject}
---

AgentMatrix 自动回复
"""

            # 创建内部 Email 对象
            email_id = IDGenerator.generate_email_id()
            email_session_id = IDGenerator.generate_session_id()

            feedback_email = Email(
                id=email_id,
                sender="System",
                recipient="User",
                subject=subject,
                body=body,
                in_reply_to=None,
                task_id="ask_user_feedback",
                sender_session_id=None,
                recipient_session_id=email_session_id,
                metadata={
                    'is_external': True,
                    'original_sender': original_sender
                }
            )

            # 通过 Email Proxy 发送
            await self.send_to_external(feedback_email)
            self.logger.info(f"📧 已发送 ask_user 反馈邮件: {message[:50]}...")

        except Exception as e:
            self.logger.error(f"❌ 发送 ask_user 反馈邮件失败: {e}", exc_info=True)


    def parse_subject(self, subject: str) -> Optional[dict]:
        """
        解析邮件subject

        Returns:
            {
                'type': 'reply' | 'new_session' | None,
                'agent_name': str,
                'task_id': str,
                'user_session_id': str,
                'agent_session_id': str,
                'clean_subject': str
            }
        """
        if not subject:
            return None

        # 1. 优先匹配复杂标记 #{agent_name}#{task_id}#{user_session_id}#{agent_session_id}#
        match = re.search(r'#([^#]+)#([^#]+)#([^#]*)#([^#]*)#', subject)
        if match:
            agent_name, task_id, user_session_id, agent_session_id = match.groups()
            clean_subject = re.sub(r'#([^#]+)#([^#]+)#([^#]*)#([^#]*)#', '', subject).strip()

            return {
                'type': 'reply',
                'agent_name': agent_name,
                'task_id': task_id,
                'user_session_id': user_session_id or None,
                'agent_session_id': agent_session_id or None,
                'clean_subject': clean_subject
            }

        # 2. 匹配新会话 @{agent_name}
        match = re.search(r'@(\w+)', subject)
        if match:
            agent_name = match.group(1)

            return {
                'type': 'new_session',
                'agent_name': agent_name,
                'task_id': None,
                'user_session_id': None,
                'agent_session_id': None,
                'clean_subject': re.sub(r'@\w+\s*', '', subject).strip()
            }

        return None

    def find_user_session_id(self, agent_name: str, task_id: str, agent_session_id: str) -> Optional[str]:
        """
        查询数据库获取user_session_id

        查询条件：
        - recipient = agent_name
        - sender = user_agent_name
        - task_id = task_id
        - recipient_session_id = agent_session_id
        - 取最新记录的sender_session_id
        """
        query = """
            SELECT sender_session_id FROM emails
            WHERE recipient = ?
              AND sender = ?
              AND task_id = ?
              AND recipient_session_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """
        cursor = self.db.conn.cursor()
        cursor.execute(query, (agent_name, self.user_agent_name, task_id, agent_session_id))
        result = cursor.fetchone()
        return result[0] if result else None

    def _resolve_reply_to_id(self, raw_email) -> Optional[str]:
        """
        从外部邮件中解析出对应的内部 email ID

        优先级：
        1. X-AgentMatrix-Email-Id 自定义 header（冗余保障）
        2. 标准 In-Reply-To SMTP header → 通过映射表查找
        """
        # 1. 尝试从自定义 header 获取
        custom_id = raw_email.get('X-AgentMatrix-Email-Id')
        if custom_id:
            self.logger.debug(f"📋 从 X-AgentMatrix-Email-Id 获取: {custom_id[:8]}")
            return custom_id.strip()

        # 2. 从标准 In-Reply-To header 通过映射表查找
        in_reply_to_header = raw_email.get('In-Reply-To')
        if in_reply_to_header:
            external_msg_id = in_reply_to_header.strip()
            internal_id = self.db.get_internal_email_id(external_msg_id)
            if internal_id:
                self.logger.debug(f"📋 从映射表查到: {external_msg_id[:20]} → {internal_id[:8]}")
                return internal_id

        return None

    async def process_external_email(self, raw_email):
        """处理外部邮件并调用UserProxyAgent.speak()"""
        # 1. 检查发件人
        from_addr = self._extract_email_address(raw_email['From'])
        if from_addr != self.user_mailbox:
            self.logger.info(f"⏭️  忽略非用户邮箱邮件: {from_addr}")
            return

        # 2. 解码subject
        subject = self._decode_header(raw_email['Subject'])
        
        # 3. 优先检查是否是 ask_user 回复
        ask_user_metadata = self._parse_ask_user_metadata(subject)
        if ask_user_metadata:
            self.logger.info("📬 检测到 ask_user 回复邮件")
            # 构造内部 Email 对象用于处理
            body, attachments = self._extract_body_and_attachments(raw_email, 'ask_user')
            
            ask_user_email = Email(
                id=IDGenerator.generate_email_id(),
                sender="User",
                recipient="System",
                subject=subject,
                body=body,
                in_reply_to=None,
                task_id="ask_user",
                sender_session_id=None,
                recipient_session_id=None,
                metadata={
                    'ask_user_metadata': ask_user_metadata,
                    'original_sender': from_addr
                }
            )
            
            await self._handle_ask_user_reply(ask_user_email)
            return

        # 4. 解析普通邮件的subject
        parsed = self.parse_subject(subject)
        if not parsed:
            self.logger.warning(f"⚠️ 无法识别的subject格式: {subject}")
            return

        self.logger.info(f"📬 处理邮件: {parsed['type']} → {parsed['agent_name']}")

        # 5. 查询user_session_id（如果为空）
        if parsed['type'] == 'reply' and not parsed['user_session_id']:
            parsed['user_session_id'] = self.find_user_session_id(
                parsed['agent_name'],
                parsed['task_id'],
                parsed['agent_session_id']
            )

        # 6. 处理新会话
        if parsed['type'] == 'new_session':
            parsed['user_session_id'] = IDGenerator.generate_session_id()
            parsed['task_id'] = parsed['user_session_id']  # 新会话 task_id = user_session_id

        # 7. 提取正文和附件
        body, attachments = self._extract_body_and_attachments(raw_email, parsed['task_id'])

        # 8. 获取UserProxyAgent
        user_agent = self.post_office.directory.get(self.user_agent_name)
        if not user_agent:
            self.logger.error(f"❌ UserProxyAgent {self.user_agent_name} 不存在")
            return

        # 9. 查找 reply_to_id（从外部邮件的 In-Reply-To 或 X-AgentMatrix-Email-Id 映射回内部 email ID）
        reply_to_id = self._resolve_reply_to_id(raw_email)

        # 10. 调用speak()
        await user_agent.speak(
            session_id=parsed['user_session_id'],
            task_id=parsed['task_id'],
            to=parsed['agent_name'],
            subject=parsed['clean_subject'],
            content=body,
            reply_to_id=reply_to_id,
            attachments=attachments
        )

        self.logger.info(f"✅ 已转发邮件到UserProxyAgent.speak()")

    async def _on_email_sent_handler(self, email: Email):
        """PostOffice hook：处理内部邮件发送"""
        self.logger.debug(f"🔔 hook 触发: {email.sender} → {email.recipient}")

        # 只处理发给User的邮件
        if email.recipient != self.user_agent_name:
            self.logger.debug(f"⏭️ 跳过（收件人不是 {self.user_agent_name}）")
            return

        # 检查是否启用
        enabled = self.config.get('enabled', False)
        self.logger.info(f"🔍 Email Proxy config.enabled = {enabled}, config keys = {list(self.config.keys())}")
        if not enabled:
            self.logger.warning(f"⚠️ Email Proxy 未启用（config.enabled=False），跳过发送到外部")
            return

        self.logger.info(f"📤 准备发送到外部: {email.sender} → {email.recipient}")
        # 发送到外部
        await self.send_to_external(email)

    async def send_ask_user_email(self, agent_name: str, agent_session_id: str, question: str):
        """
        发送 ask_user 特殊邮件（不经过 PostOffice）

        Subject 格式：请回答问题 #ASK_USER#{agent_name}#{agent_session_id}#

        Args:
            agent_name: Agent 名称
            agent_session_id: Agent 的 session_id
            question: 问题内容
        """
        try:
            # 截断过长的问题
            question_preview = question[:100] + "..." if len(question) > 100 else question
            subject = f"请回答问题 #ASK_USER#{agent_name}#{agent_session_id}#"

            # 构造邮件正文
            body = f"""你好，

{agent_name} 有一个问题需要你回答：

问题：{question}

---
请直接回复此邮件来回答问题。

---
AgentMatrix 自动回复
"""

            # 构造邮件
            msg = MIMEMultipart()
            msg['From'] = self.matrix_mailbox
            msg['To'] = self.user_mailbox
            msg['Subject'] = subject

            domain = self.matrix_mailbox.split('@')[1]
            external_message_id = IDGenerator.generate_message_id(domain)
            msg['Message-ID'] = external_message_id

            # 添加正文
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # 发送
            with smtplib.SMTP_SSL(
                self.smtp_config['host'],
                int(self.smtp_config['port'])
            ) as server:
                server.login(
                    self.smtp_config['user'],
                    self.smtp_config['password']
                )
                server.send_message(msg)

            # 保存映射（ask_user 邮件没有内部 email ID，用 email_id 占位）
            self.db.save_external_email_mapping(external_message_id, email_id)

            self.logger.info(f"📧 发送 ask_user 邮件: {agent_name} → {self.user_mailbox}")

        except Exception as e:
            self.logger.error(f"❌ 发送 ask_user 邮件失败: {e}", exc_info=True)


    async def send_to_external(self, email: Email):
        """发送内部邮件到外部邮箱"""
        try:
            # 1. 生成外部subject
            external_subject = await self._generate_external_subject(email)

            # 2. 构造邮件
            msg = MIMEMultipart()
            msg['From'] = self.matrix_mailbox
            msg['To'] = self.user_mailbox
            msg['Subject'] = external_subject

            domain = self.matrix_mailbox.split('@')[1]
            external_message_id = IDGenerator.generate_message_id(domain)
            msg['Message-ID'] = external_message_id

            # 2b. 设置 In-Reply-To（让外部邮箱正确线程化）
            if email.in_reply_to:
                parent_external_id = self.db.get_external_message_id(email.in_reply_to)
                if parent_external_id:
                    msg['In-Reply-To'] = parent_external_id

            # 2c. 设置自定义 header（冗余保障）
            msg['X-AgentMatrix-Email-Id'] = email.id

            # 3. 添加正文
            msg.attach(MIMEText(email.body, 'plain', 'utf-8'))

            # 4. 添加附件
            for att in email.metadata.get('attachments', []):
                self._add_attachment(msg, att, email.sender, email.task_id)

            # 5. 发送
            with smtplib.SMTP_SSL(
                self.smtp_config['host'],
                int(self.smtp_config['port'])
            ) as server:
                server.login(
                    self.smtp_config['user'],
                    self.smtp_config['password']
                )
                server.send_message(msg)

            # 6. 保存映射
            self.db.save_external_email_mapping(external_message_id, email.id)

            self.logger.info(f"📧 发送外部邮件: {email.sender} → {self.user_mailbox}")

        except Exception as e:
            self.logger.error(f"❌ 发送外部邮件失败: {e}", exc_info=True)

    async def _generate_external_subject(self, email: Email) -> str:
        """
        生成外部邮件的subject

        格式：
        - 普通邮件: 原始主题 #{agent_name}#{task_id}#{user_session_id}#{agent_session_id}#
        - ask_user: 原始主题 #ASK_USER#{agent_name}#{agent_session_id}#
        """
        agent_name = email.sender
        task_id = email.task_id
        agent_session_id = email.sender_session_id

        # 检查是否是 ask_user 邮件
        ask_user_metadata = email.metadata.get('ask_user_metadata')
        if ask_user_metadata:
            # ask_user 使用特殊格式
            tag = f"#ASK_USER#{agent_name}#{agent_session_id}#"
            return f"{email.subject} {tag}".strip()

        # 普通邮件使用新格式
        # 查询user_session_id
        user_session_id = await self._find_user_session_id_for_outbound(task_id, agent_session_id)

        # 构造标记
        tag = f"#{agent_name}#{task_id}#{user_session_id or ''}#{agent_session_id}#"

        return f"{email.subject} {tag}".strip()

    async def _find_user_session_id_for_outbound(self, task_id: str, agent_session_id: str) -> Optional[str]:
        """
        查询发信时需要的user_session_id

        查询 User 发给 Agent 的邮件，其中 recipient_session_id = agent_session_id，
        取最新记录的 sender_session_id 作为 user_session_id。

        语义：找到 User 发的、被 Agent 以 agent_session_id 接收的那封邮件，
        其 sender_session_id 就是 User 端的 session ID。
        """
        query = """
            SELECT sender_session_id FROM emails
            WHERE sender = ?
              AND task_id = ?
              AND recipient_session_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """
        cursor = self.db.conn.cursor()
        cursor.execute(query, (self.user_agent_name, task_id, agent_session_id))
        result = cursor.fetchone()
        return result[0] if result else None

    def _extract_body_and_attachments(self, raw_email, task_id: str) -> tuple:
        """提取邮件正文和附件"""
        body = ""
        attachments = []

        for part in raw_email.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get('Content-Disposition', ''))

            # 正文
            if content_type == 'text/plain' and 'attachment' not in content_disposition:
                charset = part.get_content_charset() or 'utf-8'
                body = part.get_payload(decode=True).decode(charset, errors='ignore')

            # 附件
            elif 'attachment' in content_disposition:
                att = self._save_attachment(part, task_id)
                if att:
                    attachments.append(att)

        return body, attachments

    def _save_attachment(self, part, task_id: str) -> Optional[dict]:
        """保存附件到User的附件目录"""
        filename = part.get_filename()
        if not filename:
            return None

        # 解码文件名
        from email.header import decode_header
        decoded_parts = decode_header(filename)
        filename = ''
        for content, encoding in decoded_parts:
            if isinstance(content, bytes):
                filename += content.decode(encoding or 'utf-8', errors='ignore')
            else:
                filename += content

        # 保存路径
        att_dir = self.paths.get_agent_attachments_dir("User", task_id)
        att_dir.mkdir(parents=True, exist_ok=True)

        file_path = att_dir / filename
        with open(file_path, 'wb') as f:
            f.write(part.get_payload(decode=True))

        return {
            'filename': filename,
            'size': file_path.stat().st_size,
            'container_path': f'/work_files/attachments/{filename}'
        }

    def _add_attachment(self, msg: MIMEMultipart, att: dict, sender: str, task_id: str):
        """添加附件到邮件"""
        filename = att['filename']

        # 查找文件
        att_dir = self.paths.get_agent_attachments_dir(sender, task_id)
        file_path = att_dir / filename

        if not file_path.exists():
            self.logger.warning(f"⚠️ 附件不存在: {file_path}")
            return

        # 读取并附加
        with open(file_path, 'rb') as f:
            part = MIMEApplication(f.read())
            part.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(part)

        self.logger.info(f"✅ 添加附件: {filename}")

    def _extract_email_address(self, email_header: str) -> str:
        """从email header中提取邮箱地址"""
        if not email_header:
            return ""

        import re
        match = re.search(r'<(.+?)>', email_header)
        if match:
            return match.group(1)

        return email_header.strip()

    def _decode_header(self, header: str) -> str:
        """解码email header"""
        if not header:
            return ""

        from email.header import decode_header
        decoded_parts = []
        for content, encoding in decode_header(header):
            if isinstance(content, bytes):
                decoded_parts.append(content.decode(encoding or 'utf-8', errors='ignore'))
            else:
                decoded_parts.append(content)

        return ''.join(decoded_parts)
