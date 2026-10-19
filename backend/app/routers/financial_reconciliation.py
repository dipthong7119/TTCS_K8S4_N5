"""SCRUM-85 financial reconciliation API for accounting reports."""

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import deny_unannotated_route, require_role
from app.database import get_db
from app.services.financial_reconciliation import get_financial_reconciliation_report

router = APIRouter(
    prefix="/reconciliation",
    tags=["financial reconciliation"],
    dependencies=[Depends(deny_unannotated_route)],
)


@router.get(
    "/financial",
    dependencies=[Depends(require_role("admin", "accountant"))],
)
def get_financial_reconciliation(
    from_date: date = Query(...),
    to_date: date = Query(...),
    station_id: int | None = Query(None, gt=0),
    charge_point_code: str | None = Query(None, min_length=1),
    status: Literal[
        "all",
        "review",
        "missing_invoice",
        "missing_ledger",
        "amount_mismatch",
        "collection_mismatch",
        "missing_pricing",
    ] = Query("all"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reconcile completed-session energy, tariff invoices, and wallet charges."""
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail="Ngày bắt đầu phải trước hoặc bằng ngày kết thúc",
        )
    return get_financial_reconciliation_report(
        db,
        from_date=from_date,
        to_date=to_date,
        station_id=station_id,
        charge_point_code=charge_point_code,
        status=status,
    )
