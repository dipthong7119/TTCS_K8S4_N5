"""API vận hành viên đổi và đọc cấu hình OCPP của trụ."""

from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.ocpp.config_keys import ConfigurationValidationError, validate_change
from app.services.charge_point_configuration import (
    ConfigurationOperationError,
    change_configuration,
    read_configuration,
)

router = APIRouter(
    prefix="/charge-points",
    tags=["charge-point-configuration"],
    dependencies=[Depends(deny_unannotated_route)],
)


class ChangeConfigurationRequest(BaseModel):
    value: Any


def _raise_operation_error(exc: ConfigurationOperationError) -> NoReturn:
    raise HTTPException(status_code=exc.http_status, detail=exc.as_payload()) from exc


@router.put(
    "/{code}/configuration/{key}",
    dependencies=[Depends(require_role("operator", "admin"))],
)
async def put_charge_point_configuration(
    code: str,
    key: str,
    body: ChangeConfigurationRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        validate_change(key, body.value)
        return await change_configuration(db, code, key, body.value, current_user.id)
    except ConfigurationValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ConfigurationOperationError as exc:
        _raise_operation_error(exc)


@router.get(
    "/{code}/configuration",
    dependencies=[Depends(require_role("operator", "admin"))],
)
async def get_charge_point_configuration(
    code: str,
    _current_user: CurrentUser,
    db: Session = Depends(get_db),
    keys: list[str] | None = Query(default=None),
) -> dict[str, Any]:
    try:
        return await read_configuration(db, code, keys)
    except ConfigurationOperationError as exc:
        _raise_operation_error(exc)
