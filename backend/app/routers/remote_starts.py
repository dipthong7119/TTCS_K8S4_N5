"""API tài xế gửi và theo dõi yêu cầu bắt đầu sạc từ xa."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.remote_start_request import RemoteStartStatus
from app.schemas.remote_start import (
    RemoteStartErrorResponse,
    RemoteStartResponse,
    RemoteStartStatusResponse,
)
from app.services.remote_start import (
    RemoteStartFailure,
    _message_for,
    get_owned_remote_start,
    seconds_left,
    submit_remote_start,
    utc_now_naive,
)


def _error_response(error: RemoteStartFailure) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=RemoteStartErrorResponse(
            detail=error.detail, code=error.code
        ).model_dump(mode="json"),
    )


class _RemoteStartRoute(APIRoute):
    """Chuẩn hóa lỗi xác thực/phân quyền cho hợp đồng API này."""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content=RemoteStartErrorResponse(
                        detail="Yêu cầu không hợp lệ.", code="invalid_request"
                    ).model_dump(mode="json"),
                )
            except HTTPException as exc:
                errors = {
                    401: ("unauthorized", "Bạn cần đăng nhập."),
                    403: ("forbidden", "Bạn không có quyền truy cập."),
                    404: ("not_found", "Không tìm thấy tài nguyên."),
                    409: ("conflict", "Yêu cầu hiện không thể thực hiện."),
                    422: ("invalid_request", "Yêu cầu không hợp lệ."),
                }
                code, detail = errors.get(
                    exc.status_code,
                    ("request_failed", "Không thể xử lý yêu cầu."),
                )
                return JSONResponse(
                    status_code=exc.status_code,
                    content=RemoteStartErrorResponse(
                        detail=detail, code=code
                    ).model_dump(mode="json"),
                )

        return handle


router = APIRouter(
    dependencies=[Depends(deny_unannotated_route)],
    tags=["driver remote start"],
    route_class=_RemoteStartRoute,
)
_DRIVER_ONLY = [Depends(require_role("driver"))]


@router.post(
    "/connectors/{connector_id}/remote-start",
    response_model=RemoteStartResponse,
    status_code=202,
    dependencies=_DRIVER_ONLY,
    responses={
        200: {"model": RemoteStartResponse, "description": "Yêu cầu đang hoạt động đã tồn tại"},
        202: {"model": RemoteStartResponse, "description": "Trụ đã nhận lệnh"},
        401: {"model": RemoteStartErrorResponse, "description": "Cần đăng nhập"},
        403: {"model": RemoteStartErrorResponse, "description": "Sai vai trò"},
        404: {"model": RemoteStartErrorResponse, "description": "Không tìm thấy đầu nối"},
        409: {"model": RemoteStartErrorResponse, "description": "Trạm, trụ hoặc đầu nối chưa sẵn sàng"},
        502: {"model": RemoteStartErrorResponse, "description": "Trụ từ chối hoặc báo lỗi"},
        504: {"model": RemoteStartErrorResponse, "description": "Trụ hết thời gian phản hồi"},
    },
)
async def create_remote_start(
    connector_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> RemoteStartResponse | JSONResponse:
    """Tạo yêu cầu và gửi lệnh, không tạo phiên thay cho trụ."""
    driver_user_id = current_user.id
    try:
        request_row, sent = await submit_remote_start(db, connector_id, driver_user_id)
    except RemoteStartFailure as exc:
        return _error_response(exc)

    status_code = (
        202
        if sent and request_row.status == RemoteStartStatus.WAITING_START
        else 200
    )
    return JSONResponse(
        status_code=status_code,
        content=RemoteStartResponse(
            id=request_row.id,
            status=request_row.status,
            expires_at=request_row.expires_at,
            seconds_left=seconds_left(request_row.expires_at, utc_now_naive()),
            message=_message_for(request_row.status),
        ).model_dump(mode="json"),
    )


@router.get(
    "/remote-starts/{request_id}",
    response_model=RemoteStartStatusResponse,
    dependencies=_DRIVER_ONLY,
    responses={
        401: {"model": RemoteStartErrorResponse, "description": "Cần đăng nhập"},
        403: {
            "model": RemoteStartErrorResponse,
            "description": "Không có quyền xem yêu cầu",
        },
    },
)
async def read_remote_start(
    request_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> RemoteStartStatusResponse | JSONResponse:
    """Trả trạng thái riêng của tài xế đăng nhập."""
    try:
        request_row, connector_number, now = get_owned_remote_start(
            db, request_id, current_user.id
        )
    except RemoteStartFailure as exc:
        return _error_response(exc)

    return RemoteStartStatusResponse(
        id=request_row.id,
        status=request_row.status,
        connector_id=connector_number,
        expires_at=request_row.expires_at,
        seconds_left=(
            seconds_left(request_row.expires_at, now)
            if request_row.status == RemoteStartStatus.WAITING_START
            else None
        ),
        session_id=request_row.session_id,
        message=_message_for(request_row.status),
    )
