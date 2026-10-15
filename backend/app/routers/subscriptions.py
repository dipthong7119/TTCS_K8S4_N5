"""Driver subscription and platform-wide monthly package APIs (SCRUM-68)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.driver_subscription import DriverSubscription
from app.models.subscription_plan import SubscriptionPlan
from app.schemas.subscription import (
    SubscribeRequest,
    SubscriptionPlanCreate,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdate,
)
from app.services.subscriptions import (
    InsufficientSubscriptionBalance,
    SubscriptionConflict,
    create_plan,
    get_current_subscription,
    list_active_plans,
    list_owner_revenue_share,
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
    """Show the owner's proportional 60% share for package charging usage."""
    return list_owner_revenue_share(db, current_user.id)
