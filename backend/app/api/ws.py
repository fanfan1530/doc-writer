"""WebSocket 端点 —— 实时通知推送。"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.auth import decode_token
from app.services.notification_service import ws_connect, ws_disconnect

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/notifications")
async def ws_notifications(ws: WebSocket, token: str = Query(...)):
    """通知推送 WebSocket。客户端连接时通过 query string 传递 JWT token。

    连接: ws://host:8091/ws/notifications?token=<jwt_access_token>
    """
    # 验证 token
    try:
        payload = decode_token(token)
    except Exception:
        await ws.close(code=4001, reason="无效的认证令牌")
        return

    user_id = payload.get("user_id", 0)
    if not user_id:
        await ws.close(code=4001, reason="无法识别用户")
        return

    await ws.accept()
    ws_connect(user_id, ws)

    try:
        while True:
            # 保持连接，等待客户端消息（心跳检测）
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket 异常: %s", str(e)[:100])
    finally:
        ws_disconnect(user_id, ws)
