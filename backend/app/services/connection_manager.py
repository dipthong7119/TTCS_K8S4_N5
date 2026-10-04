import asyncio
import logging
import uuid

from fastapi import WebSocket

from app.config import settings
from app.services.ocpp_parser import OCPPError, pack_call

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # charge_point_code -> WebSocket
        self.active_connections: dict[str, WebSocket] = {}
        self.pending_calls: dict[tuple[str, str], asyncio.Future] = {}
        self._pending_websockets: dict[tuple[str, str], WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, charge_point_code: str, websocket: WebSocket):
        async with self._lock:
            old_ws = self.active_connections.get(charge_point_code)
            self.active_connections[charge_point_code] = websocket
            self._fail_pending(
                charge_point_code, ConnectionError("Charge point reconnected")
            )
        if old_ws and old_ws is not websocket:
            logger.info(
                "Charge point connection replaced: code=%s old_connection_id=%s new_connection_id=%s",
                charge_point_code,
                id(old_ws),
                id(websocket),
            )
            try:
                await old_ws.close(code=1000, reason="New connection opened")
            except Exception:
                logger.debug(
                    "Could not close the previous charge point websocket", exc_info=True
                )

    def disconnect(self, charge_point_code: str, websocket: WebSocket):
        if self.active_connections.get(charge_point_code) == websocket:
            del self.active_connections[charge_point_code]
            self._fail_pending(
                charge_point_code, ConnectionError("Charge point disconnected")
            )

    async def send_to(self, charge_point_code: str, text: str):
        websocket = self.active_connections.get(charge_point_code)
        if websocket is None:
            raise ConnectionError("Charge point is offline")
        await websocket.send_text(text)

    async def send_call(
        self,
        charge_point_code: str,
        action: str,
        payload: dict,
        timeout: float | None = None,
    ) -> dict:
        websocket = self.active_connections.get(charge_point_code)
        if websocket is None:
            raise ConnectionError("Charge point is offline")

        message_id = uuid.uuid4().hex
        key = (charge_point_code, message_id)
        future = asyncio.get_running_loop().create_future()
        self.pending_calls[key] = future
        self._pending_websockets[key] = websocket
        try:
            if self.active_connections.get(charge_point_code) is not websocket:
                raise ConnectionError(
                    "Charge point reconnected before command was sent"
                )
            try:
                await websocket.send_text(pack_call(message_id, action, payload))
            except Exception as exc:
                raise ConnectionError("Charge point connection was lost") from exc
            wait_seconds = (
                timeout
                if timeout is not None
                else settings.OCPP_REMOTE_CALL_TIMEOUT_SECONDS
            )
            return await asyncio.wait_for(future, timeout=wait_seconds)
        finally:
            self.pending_calls.pop(key, None)
            self._pending_websockets.pop(key, None)

    async def resolve_call_result(
        self,
        charge_point_code: str,
        message_id: str,
        payload: dict,
        websocket: WebSocket | None = None,
    ) -> bool:
        key = (charge_point_code, message_id)
        future = self.pending_calls.get(key)
        if future is None or future.done():
            return False
        if websocket is not None and self._pending_websockets.get(key) is not websocket:
            return False
        future.set_result(payload)
        return True

    async def resolve_call_error(
        self,
        charge_point_code: str,
        message_id: str,
        error_code: str,
        description: str,
        details: dict,
        websocket: WebSocket | None = None,
    ) -> bool:
        key = (charge_point_code, message_id)
        future = self.pending_calls.get(key)
        if future is None or future.done():
            return False
        if websocket is not None and self._pending_websockets.get(key) is not websocket:
            return False
        future.set_exception(OCPPError(error_code, description, details, message_id))
        return True

    def _fail_pending(self, charge_point_code: str, error: Exception) -> None:
        for key, future in tuple(self.pending_calls.items()):
            if key[0] == charge_point_code and not future.done():
                future.set_exception(error)


manager = ConnectionManager()
