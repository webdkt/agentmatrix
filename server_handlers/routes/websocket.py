"""
WebSocket route and broadcast endpoint.
"""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..state import server_state

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()
    server_state.active_websockets.append(websocket)

    try:
        if server_state.matrix_runtime and hasattr(server_state.matrix_runtime, "status_collector"):
            status = server_state.matrix_runtime.status_collector.collect_status()
            await websocket.send_text(
                json.dumps({"type": "SYSTEM_STATUS", "data": status})
            )

        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get("type", "")

                if msg_type == "REQUEST_SYSTEM_STATUS":
                    if server_state.matrix_runtime and hasattr(
                        server_state.matrix_runtime, "status_collector"
                    ):
                        status = server_state.matrix_runtime.status_collector.collect_status()
                        await websocket.send_text(
                            json.dumps({"type": "SYSTEM_STATUS", "data": status})
                        )
                else:
                    await websocket.send_text(
                        json.dumps({"type": "echo", "data": message})
                    )
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Invalid JSON"})
                )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"⚠️ WebSocket error: {e}")
    finally:
        if websocket in server_state.active_websockets:
            server_state.active_websockets.remove(websocket)
