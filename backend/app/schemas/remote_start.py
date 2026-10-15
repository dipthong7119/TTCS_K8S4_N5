"""Schemas API bắt đầu phiên sạc từ ứng dụng."""

from datetime import datetime

from pydantic import BaseModel

from app.models.remote_start_request import RemoteStartStatus


class RemoteStartErrorResponse(BaseModel):
    detail: str
    code: str
    minimum_required_vnd: int | None = None
    top_up_url: str | None = None


class RemoteStartResponse(BaseModel):
    id: int
    status: RemoteStartStatus
    expires_at: datetime | None
    seconds_left: int | None
    message: str


class RemoteStartStatusResponse(RemoteStartResponse):
    connector_id: int
    session_id: int | None
