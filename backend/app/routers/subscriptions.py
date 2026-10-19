"""Driver subscription and platform-wide monthly package APIs (SCRUM-68)."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.driver_subscription import DriverSubscription
from app.models.subscription_plan import SubscriptionPlan
from app.schemas.revenue_share import RevenueShareContractCreate
from app.schemas.subscription import (
    SubscribeRequest,
    SubscriptionPlanCreate,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdate,
)
from app.services.audit import append_audit
from app.services.subscriptions import (
    InsufficientSubscriptionBalance,
    SubscriptionConflict,
    create_plan,
    create_revenue_share_contract,
    get_current_subscription,
    list_active_plans,
    list_owner_revenue_share,
    list_revenue_share_contracts,
    list_revenue_share_report,
    list_user_subscriptions,
    purchase_subscription,
    update_plan,
    utc_now_naive,
)

router = APIRouter(
    prefix="/subscriptions",
    tags=["subscriptions"],
    dependencies=[Depends(deny_unannotated_route)],
)


def _serialize_subscription(
    item: DriverSubscription, *, now: datetime | None = None
) -> dict:
    if now is None:
        now = utc_now_naive()
    return {
        "id": item.id,
        "plan_id": item.plan_id,
        "plan_name": item.plan_name,
        "monthly_fee_vnd": item.monthly_fee_vnd,
        "price_vnd_per_kwh": item.price_vnd_per_kwh,
        "starts_at": item.starts_at.isoformat() + "Z",
        "expires_at": item.expires_at.isoformat() + "Z",
        "is_active": item.starts_at <= now < item.expires_at,
        "auto_renew": False,
    }


@router.get("/plans", dependencies=[Depends(require_role("driver", "admin"))])
async def get_plans(db: Session = Depends(get_db)):
    """List active plans available to drivers at every station."""
    return [SubscriptionPlanResponse.model_validate(plan) for plan in list_active_plans(db)]


@router.post(
    "/plans",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def add_plan(
    body: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
):
    try:
        plan = create_plan(db, body.model_dump())
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên gói đã được sử dụng") from exc
    return SubscriptionPlanResponse.model_validate(plan)


@router.patch(
    "/plans/{plan_id}", dependencies=[Depends(require_role("admin"))]
)
async def edit_plan(
    plan_id: int,
    body: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy gói thuê bao")
    try:
        plan = update_plan(db, plan, body.model_dump(exclude_unset=True))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên gói đã được sử dụng") from exc
    return SubscriptionPlanResponse.model_validate(plan)


@router.get("/mine", dependencies=[Depends(require_role("driver"))])
async def get_my_subscriptions(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    history = list_user_subscriptions(db, current_user.id)
    current = get_current_subscription(db, current_user.id)
    return {
        "active_subscription": _serialize_subscription(current) if current else None,
        "subscriptions": [_serialize_subscription(item) for item in history],
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("driver"))],
)
async def subscribe(
    body: SubscribeRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    try:
        subscription = purchase_subscription(db, current_user.id, body.plan_id)
        db.commit()
    except InsufficientSubscriptionBalance as exc:
        db.rollback()
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except SubscriptionConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Đăng ký gói bị trùng; hãy tải lại trạng thái") from exc
    db.refresh(subscription)
    return _serialize_subscription(subscription)


@router.get(
    "/revenue-share/mine",
    dependencies=[Depends(require_role("station_owner"))],
)
async def get_my_revenue_share(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Show the owner's proportional share under the effective contracts."""
    return list_owner_revenue_share(db, current_user.id)


@router.get(
    "/revenue-share",
    dependencies=[Depends(require_role("admin", "accountant"))],
)
async def get_revenue_share_report(
    date_from: date,
    date_to: date,
    station_owner_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Admin/accountant report for contract-based subscription revenue shares."""
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
    return list_revenue_share_report(
        db, date_from, date_to, station_owner_id=station_owner_id
    )


@router.get(
    "/revenue-share/contracts",
    dependencies=[Depends(require_role("admin", "accountant"))],
)
async def get_revenue_share_contracts(
    station_owner_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_revenue_share_contracts(db, station_owner_id)


@router.post(
    "/revenue-share/contracts",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "accountant"))],
)
async def add_revenue_share_contract(
    body: RevenueShareContractCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    try:
        contract = create_revenue_share_contract(
            db,
            station_owner_id=body.station_owner_id,
            partner_share_percent=body.partner_share_percent,
            platform_share_percent=body.platform_share_percent,
            effective_from=body.effective_from,
            created_by=current_user.id,
        )
        append_audit(
            db,
            action="revenue_share_contract.created",
            object_type="revenue_share_contract",
            object_id=contract.id,
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_name=current_user.full_name,
            details={
                "station_owner_id": contract.station_owner_id,
                "partner_share_percent": str(contract.partner_share_percent),
                "platform_share_percent": str(contract.platform_share_percent),
                "effective_from": contract.effective_from.isoformat() + "Z",
            },
        )
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Hợp đồng chia doanh thu bị trùng") from exc
    db.refresh(contract)
    contract_data = list_revenue_share_contracts(db, contract.station_owner_id)
    return next(item for item in contract_data["items"] if item["id"] == contract.id)
