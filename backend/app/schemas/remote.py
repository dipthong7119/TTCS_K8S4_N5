from typing import Literal

from pydantic import BaseModel, Field


class ResetRequest(BaseModel):
    type: Literal["Soft", "Hard"] = "Soft"


class RemoteStartRequest(BaseModel):
    connector_id: int | None = Field(
        default=None,
        ge=1,
        description="ID đầu nối (connectorId trong OCPP 1.6). Nếu bỏ trống, trụ tự chọn.",
    )
    id_tag: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Mã thẻ RFID / ID Tag của người dùng (tối đa 20 ký tự).",
    )


class RemoteCommandResponse(BaseModel):
    status: Literal["Accepted", "Rejected"]
    message: str
