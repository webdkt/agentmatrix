import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from core.loader import AgentLoader

from core.runtime import AgentMatrix

from agents.post_office import PostOffice

from backends.mock_llm import MockLLM
from core.message import Email

agentMatrix = None

active_websockets = []

# === 生命周期 ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    
    
    # 2. 注入事件回调 (让 Agent 能通过 WS 说话)
    async def global_event_handler(event):
        #msg = {"type": "EVENT", "payload": event.to_dict()}
        # 广播给所有前端
        msg = json.dumps(event.to_dict())
        #print(msg)
        for ws in active_websockets:
            try:
                await ws.send_text(msg)
            except:
                pass

    agentMatrix = AgentMatrix(agent_profile_path="./profiles",  event_call_back=global_event_handler)
    agentMatrix.load_matrix('Samples/TestWorkspace')
    
    yield
    
    agentMatrix.save_matrix()
    

app = FastAPI(lifespan=lifespan)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            #print(msg)
            if msg.get("type") == "START_TASK":
                prompt = "start_task:" + msg.get("content") # 触发 Mock 关键词
                
                # 发送第一封信给 Planner
                email = Email(
                    sender="User",
                    recipient="Planner",
                    subject="New Project",
                    body=prompt # 包含 "start_task"
                )
                await agentMatrix.post_office.dispatch(email)
                await websocket.send_text(json.dumps({"type": "SYSTEM", "msg": "Task Submitted"}))
                
    except WebSocketDisconnect:
        active_websockets.remove(websocket)


# 简单路由返回 client.html
@app.get("/")
async def get():
    with open("client.html", "r", encoding='utf-8') as f:
        return HTMLResponse(f.read())


# 获取系统概览 (Dashboard)
@app.get("/api/system/status")
async def get_system_status():
    """返回所有 Agent 的实时状态快照"""
    overview = []
    
    # 遍历所有注册的 Agent
    for name, agent in post_office.directory.items():
        snapshot = agent.get_snapshot()
        overview.append(snapshot)
        
    return {"agents": overview}


# 获取某个 Agent 的详细上下文 (Deep Dive)
@app.get("/api/agents/{agent_name}/context")
async def get_agent_context(agent_name: str):
    agent = post_office.directory.get(agent_name)
    if not agent:
        return {"error": "Agent not found"}
    # 这里返回更详细的内存数据，包括完整的对话历史
    # 注意：生产环境要注意隐私和数据量
    return agent.sessions 


# 获取邮箱历史 (Mailbox)
@app.get("/api/agents/{agent_name}/mailbox")
async def get_agent_mailbox(agent_name: str, limit: int = 20):
    """从 SQLite 读取历史邮件"""
    emails = db.get_mailbox(agent_name, limit)
    return {"emails": emails}

