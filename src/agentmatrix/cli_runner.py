# cli_runner.py
import asyncio
from agentmatrix import AgentMatrix
from agentmatrix import Email
import logging
import uuid
logger = logging.getLogger('CLI_Runner')
# 1. 定义：收到信时干什么？-> 打印出来

mail_id_sender_map = {}  # 记录邮件 ID 到发送者的映射

async def print_to_console(email: Email):
    f = f"""
    📨 [New Mail] From {email.sender}: "
        Subject: {email.subject}"
        Body: {email.body}"
        MsgID: {email.id}
        >> 请输入回复 (格式: To_Agent: Content) 或 'exit':"
    """
    mail_id_sender_map[email.id] = email.sender  # 记录映射
    loop = asyncio.get_running_loop()

    await loop.run_in_executor(None, logger.debug, f)


def global_event_handler(event):
    print(f"🔔 事件触发: {event}")

async def main():
    # 2. 初始化 Matrix
    matrix = AgentMatrix(agent_profile_path="./profiles", matrix_path='../../Samples/TestWorkspace', async_event_callback=global_event_handler)
    #matrix.load_matrix('Samples/TestWorkspace')
    
    # 3. 挂载回调：把我们的打印函数挂给 UserProxy
    matrix.agents["User"].on_mail_received = print_to_console
    
    await asyncio.to_thread(print, ">>> 系统启动。可以在下面输入指令。")
    await asyncio.to_thread(print, ">>> 例如: Planner: 帮我分析数据")
    
    # 4. 主循环：监听键盘输入 (这是在主线程，不会阻塞 Matrix 的后台 asyncio)
    # 注意：在 asyncio 程序里做 input() 是个 tricky 的事情，
    # 生产环境通常用 aioconsole，这里为了演示简单处理
    
    loop = asyncio.get_event_loop()
    
    import sys
    from aioconsole import ainput # pip install aioconsole
    user_session_id = str(uuid.uuid4())
    while True:
        try:
            user_input = await ainput(">> ") # 异步等待输入
            
            if user_input.lower() == "exit":
                await matrix.save_matrix()
                break

            if user_input.lower() == "new session":
                user_session_id = str(uuid.uuid4())
                await asyncio.to_thread(print, f"✅ 新会话开始 ID: {user_session_id}")
                continue

            if user_input.lower().startswith("reply:"):
                parts = user_input.split(":")
                if len(parts) < 3:
                    await asyncio.to_thread(print, "❌ 回复格式错误，请使用 'reply: MsgID: Content'")
                    continue
                reply_to_id = parts[1].strip()
                content = ":".join(parts[2:]).strip()
                if reply_to_id not in mail_id_sender_map:
                    await asyncio.to_thread(print, f"❌ 未找到消息 ID: {reply_to_id}")
                    continue
                target = mail_id_sender_map[reply_to_id]
                await matrix.agents["User"].speak(
                    user_session_id=user_session_id,
                    to=target,
                    subject=f"Re: 回复您的消息 {reply_to_id}",
                    content=content,
                    reply_to_id=reply_to_id
                )
                continue

                
            if ":" in user_input:
                target, content = user_input.split(":", 1)
                # 5. 调用 UserProxy 说话
                await matrix.agents["User"].speak(user_session_id, target.strip(), content.strip())
            else:
                await asyncio.to_thread(print,"❌ 格式错误，请使用 'Target: Content'")
                
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    asyncio.run(main())