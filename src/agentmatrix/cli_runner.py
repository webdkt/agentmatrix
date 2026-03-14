"!!! 过时待删除或者重做 !!!"
# cli_runner.py
import asyncio
from agentmatrix import AgentMatrix
from agentmatrix import Email
import logging
import uuid
from pathlib import Path
import yaml

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


def load_user_agent_name_from_config(matrix_path: str) -> str:
    """Load user agent name from matrix_world.yml configuration file"""
    config_path = Path(matrix_path) / "matrix_world.yml"
    if not config_path.exists():
        print("⚠️  Warning: matrix_world.yml not found, using default 'User'")
        return "User"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            user_name = config.get('user_agent_name', 'User')
            return user_name
    except Exception as e:
        print(f"⚠️  Error loading matrix_world.yml: {e}, using default 'User'")
        return "User"


async def main():
    # 2. 初始化 Matrix
    matrix_path = '../../Samples/TestWorkspace'
    user_agent_name = load_user_agent_name_from_config(matrix_path)

    matrix = AgentMatrix(
        agent_profile_path="./profiles",
        matrix_path=matrix_path,
        async_event_callback=global_event_handler,
        user_agent_name=user_agent_name
    )
    #matrix.load_matrix('Samples/TestWorkspace')

    # 3. 挂载回调：把我们的打印函数挂给 UserProxy
    matrix.agents[user_agent_name].on_mail_received = print_to_console
    
    await asyncio.to_thread(print, ">>> 系统启动。可以在下面输入指令。")
    await asyncio.to_thread(print, ">>> 例如: Planner: 帮我分析数据")
    
    # 4. 主循环：监听键盘输入 (这是在主线程，不会阻塞 Matrix 的后台 asyncio)
    # 注意：在 asyncio 程序里做 input() 是个 tricky 的事情，
    # 生产环境通常用 aioconsole，这里为了演示简单处理
    
    loop = asyncio.get_event_loop()
    
    import sys
    from aioconsole import ainput # pip install aioconsole
    task_id = str(uuid.uuid4())
    while True:
        try:
            user_input = await ainput(">> ") # 异步等待输入
            
            if user_input.lower() == "exit":
                await matrix.save_matrix()
                break

            if user_input.lower() == "new session":
                task_id = str(uuid.uuid4())
                await asyncio.to_thread(print, f"✅ 新会话开始 ID: {task_id}")
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
                user_agent_name = matrix.get_user_agent_name()
                await matrix.agents[user_agent_name].speak(
                    task_id=task_id,
                    to=target,
                    subject=f"Re: 回复您的消息 {reply_to_id}",
                    content=content,
                    reply_to_id=reply_to_id
                )
                continue


            if ":" in user_input:
                target, content = user_input.split(":", 1)
                # 5. 调用 UserProxy 说话
                user_agent_name = matrix.get_user_agent_name()
                await matrix.agents[user_agent_name].speak(task_id, target.strip(), content.strip())
            else:
                await asyncio.to_thread(print,"❌ 格式错误，请使用 'Target: Content'")
                
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    asyncio.run(main())