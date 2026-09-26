import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # charge_point_code -> WebSocket
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, charge_point_code: str, websocket: WebSocket):
        if charge_point_code in self.active_connections:
            # T-28: Thay thế khi trùng mã, đóng kết nối cũ
            old_ws = self.active_connections[charge_point_code]
            try:
                # Đóng kết nối cũ với mã chuẩn, ví dụ 1000 (Normal Closure) hoặc 1008 (Policy Violation)
                # Đề bài: kết nối cũ bị đóng
                await old_ws.close(code=1000, reason="New connection opened")
            except Exception:
                logger.debug("Could not close the previous charge point websocket", exc_info=True)
        self.active_connections[charge_point_code] = websocket

    def disconnect(self, charge_point_code: str, websocket: WebSocket):
        if self.active_connections.get(charge_point_code) == websocket:
            del self.active_connections[charge_point_code]

    async def send_to(self, charge_point_code: str, text: str):
        if charge_point_code in self.active_connections:
            await self.active_connections[charge_point_code].send_text(text)
            
manager = ConnectionManager()
