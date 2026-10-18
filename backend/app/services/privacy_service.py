"""
Service: privacy_service
Tham chiếu: SCRUM-92 / S-57 — Tài xế yêu cầu xoá dữ liệu cá nhân và lịch sử di chuyển (Nghị định 13/2023/NĐ-CP).
Quy tắc:
- Không truy được tài xế đã sạc ở đâu lúc nào: phiên sạc (ChargingSession) được ẩn danh hóa.
- Doanh thu tổng hợp và sổ cái (wallet_ledger) giữ nguyên vẹn (Luật Kế toán).
- Ví còn số dư dương phải xử lý hoàn tiền trước khi duyệt.
- Mọi thao tác đều được ghi nhật ký kiểm toán (audit_logs).
"""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.charging_session import ChargingSession
from app.models.data_erasure import DataErasureRequest
from app.models.id_tag import IdTag
from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User
from app.schemas.data_erasure import DataErasureResponse
from app.services.audit import append_audit
from app.services.wallet import wallet_totals


def to_erasure_response(req: DataErasureRequest) -> DataErasureResponse:
    """Chuyển đổi ORM entity DataErasureRequest sang DataErasureResponse."""
    driver_name = req.user.full_name if req.user else None
    driver_email = req.user.email if req.user else None
    processor_name = req.processor.full_name if req.processor else None

    return DataErasureResponse(
        id=req.id,
        user_id=req.user_id,
        driver_name=driver_name,
        driver_email=driver_email,
        status=req.status,
        request_reason=req.request_reason,
        rejection_reason=req.rejection_reason,
        requested_at=req.requested_at,
        processed_at=req.processed_at,
        processed_by=req.processed_by,
        processor_name=processor_name,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


def create_erasure_request(
    db: Session, driver: User, reason: str | None = None
) -> DataErasureRequest:
    """
    Tài xế gửi yêu cầu xóa/ẩn danh hóa dữ liệu cá nhân (SCRUM-92 / S-57).
    Kiểm tra điều kiện:
    - Không có phiên sạc đang chạy.
    - Không có đặt chỗ đang chờ/đang hoạt động.
    - Ví không còn số dư dương.
    - Không có yêu cầu đang ở trạng thái pending.
    """
    # 1. Kiểm tra phiên sạc đang hoạt động
    active_session = (
        db.query(ChargingSession)
        .filter(
            ChargingSession.user_id == driver.id,
            ChargingSession.status == "active",
        )
        .first()
    )
    if active_session:
        raise HTTPException(
            status_code=400,
            detail="Không thể gửi yêu cầu xóa dữ liệu khi có phiên sạc đang hoạt động.",
        )

    # 2. Kiểm tra đặt chỗ chưa hoàn tất
    active_reservation = (
        db.query(Reservation)
        .filter(
            Reservation.user_id == driver.id,
            Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.ACTIVE]),
        )
        .first()
    )
    if active_reservation:
        raise HTTPException(
            status_code=400,
            detail="Không thể gửi yêu cầu xóa dữ liệu khi có đặt chỗ chưa hoàn tất hoặc chưa hủy.",
        )

    # 3. Kiểm tra số dư ví (quy định S-57: ví còn số dư dương thì phải xử lý hoàn tiền trước)
    totals = wallet_totals(db, driver.id)
    balance_vnd = totals.get("balance_vnd", 0)
    if balance_vnd > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Ví tài xế còn số dư ({balance_vnd:,} đ). "
                "Vui lòng hoàn tiền hoặc rút hết số dư về 0 trước khi yêu cầu xóa dữ liệu."
            ),
        )

    # 4. Chống trùng lặp (Idempotency)
    existing_pending = (
        db.query(DataErasureRequest)
        .filter(
            DataErasureRequest.user_id == driver.id,
            DataErasureRequest.status == "pending",
        )
        .first()
    )
    if existing_pending:
        raise HTTPException(
            status_code=409,
            detail="Bạn đã có một yêu cầu xóa dữ liệu đang chờ xử lý.",
        )

    clean_reason = reason.strip() if reason else None
    req = DataErasureRequest(
        user_id=driver.id,
        request_reason=clean_reason,
        status="pending",
    )
    db.add(req)
    db.flush()

    append_audit(
        db=db,
        action="privacy.request_created",
        object_type="data_erasure_request",
        object_id=req.id,
        actor_id=driver.id,
        actor_email=driver.email,
        actor_name=driver.full_name,
        target_user_id=driver.id,
        details={
            "driver_id": driver.id,
            "request_reason": clean_reason,
            "status": "pending",
        },
    )
    db.commit()
    db.refresh(req)
    return req


def get_my_erasure_requests(db: Session, driver_id: int) -> list[DataErasureRequest]:
    """Lấy danh sách các yêu cầu xóa dữ liệu của tài xế đang đăng nhập."""
    return (
        db.query(DataErasureRequest)
        .filter(DataErasureRequest.user_id == driver_id)
        .order_by(DataErasureRequest.requested_at.desc())
        .all()
    )


def list_erasure_requests(
    db: Session,
    status: str | None = None,
    driver_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[DataErasureRequest], int]:
    """Danh sách các yêu cầu xóa dữ liệu cho quản trị viên/vận hành."""
    query = db.query(DataErasureRequest)
    if status:
        query = query.filter(DataErasureRequest.status == status)
    if driver_id:
        query = query.filter(DataErasureRequest.user_id == driver_id)

    total = query.count()
    items = (
        query.order_by(DataErasureRequest.requested_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def approve_erasure_request(
    db: Session, request_id: int, admin_user: User
) -> DataErasureRequest:
    """
    Quản trị viên phê duyệt và kích hoạt ẩn danh hóa dữ liệu cá nhân theo NĐ 13/2023/NĐ-CP.
    Thực hiện:
    1. Kiểm tra lại điều kiện ví và phiên sạc.
    2. Ẩn danh hóa ChargingSession (user_id = NULL, driver_name = 'ANONYMIZED', id_tag = NULL) - dữ liệu di chuyển bị xóa hoàn toàn.
    3. Khóa và làm mất danh tính thẻ RFID (id_tags).
    4. Ẩn danh hóa đặt chỗ (reservations).
    5. Vô hiệu hóa tài khoản User và ghi đè thông tin cá nhân.
    6. Bảo toàn hóa đơn (charging_invoices) và sổ cái (wallet_ledger) theo luật kế toán.
    7. Ghi audit log.
    """
    req = (
        db.query(DataErasureRequest)
        .filter(DataErasureRequest.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy yêu cầu xóa dữ liệu."
        )

    if req.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Yêu cầu đã ở trạng thái '{req.status}', không thể phê duyệt lại.",
        )

    target_user = db.query(User).filter(User.id == req.user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy người dùng của yêu cầu này."
        )

    # Kiểm tra an toàn trước khi duyệt
    active_session = (
        db.query(ChargingSession)
        .filter(
            ChargingSession.user_id == target_user.id,
            ChargingSession.status == "active",
        )
        .first()
    )
    if active_session:
        raise HTTPException(
            status_code=400,
            detail="Tài xế hiện có phiên sạc đang hoạt động, không thể thực hiện ẩn danh hóa.",
        )

    totals = wallet_totals(db, target_user.id)
    balance_vnd = totals.get("balance_vnd", 0)
    if balance_vnd > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Ví tài xế còn số dư ({balance_vnd:,} đ). "
                "Cần hoàn tiền về 0 trước khi duyệt yêu cầu xóa dữ liệu."
            ),
        )

    # 1. Ẩn danh hóa toàn bộ các phiên sạc của tài xế
    # Số liệu trạm, sản lượng kWh, khung giờ sạc và doanh thu vẫn bảo toàn 100%
    sessions = (
        db.query(ChargingSession)
        .filter(ChargingSession.user_id == target_user.id)
        .all()
    )
    for s in sessions:
        s.user_id = None
        s.driver_name = "ANONYMIZED"
        s.id_tag = None
        s.id_tag_id = None

    # 2. Khóa và ẩn danh hóa thẻ RFID
    tags = db.query(IdTag).filter(IdTag.user_id == target_user.id).all()
    for tag in tags:
        tag.is_blocked = True
        tag.id_tag = f"ANON_{tag.id}_{uuid4().hex[:6]}"

    # 3. Ẩn danh hóa đặt chỗ lịch sử
    reservations = (
        db.query(Reservation).filter(Reservation.user_id == target_user.id).all()
    )
    for r in reservations:
        r.id_tag = "ANONYMOUS"
        r.id_tag_id = None

    # 4. Vô hiệu hóa tài khoản người dùng và ghi đè thông tin định danh
    target_user.is_active = False
    target_user.full_name = "Người dùng ẩn danh"
    anon_suffix = uuid4().hex[:6]
    target_user.email = f"anonymized_{target_user.id}_{anon_suffix}@privacy.local"
    target_user.password_hash = "ANONYMIZED_ACCOUNT_DELETED"
    target_user.failed_login_count = 0
    target_user.locked_until = None
    target_user.last_failed_ip = None

    # 5. Cập nhật trạng thái yêu cầu
    req.status = "approved"
    req.processed_at = datetime.now(UTC).replace(tzinfo=None)
    req.processed_by = admin_user.id

    # 6. Ghi nhật ký kiểm toán
    append_audit(
        db=db,
        action="privacy.request_approved",
        object_type="data_erasure_request",
        object_id=req.id,
        actor_id=admin_user.id,
        actor_email=admin_user.email,
        actor_name=admin_user.full_name,
        target_user_id=target_user.id,
        details={
            "driver_id": target_user.id,
            "anonymized_sessions_count": len(sessions),
            "anonymized_tags_count": len(tags),
            "anonymized_reservations_count": len(reservations),
            "status": "approved",
        },
    )

    db.commit()
    db.refresh(req)
    return req


def reject_erasure_request(
    db: Session, request_id: int, admin_user: User, rejection_reason: str
) -> DataErasureRequest:
    """
    Quản trị viên từ chối yêu cầu xóa dữ liệu với lý do cụ thể.
    """
    req = (
        db.query(DataErasureRequest)
        .filter(DataErasureRequest.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy yêu cầu xóa dữ liệu."
        )

    if req.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Yêu cầu đã ở trạng thái '{req.status}', không thể từ chối.",
        )

    clean_reason = rejection_reason.strip() if rejection_reason else ""
    if not clean_reason:
        raise HTTPException(
            status_code=400, detail="Bắt buộc phải nhập lý do khi từ chối yêu cầu."
        )

    req.status = "rejected"
    req.rejection_reason = clean_reason
    req.processed_at = datetime.now(UTC).replace(tzinfo=None)
    req.processed_by = admin_user.id

    append_audit(
        db=db,
        action="privacy.request_rejected",
        object_type="data_erasure_request",
        object_id=req.id,
        actor_id=admin_user.id,
        actor_email=admin_user.email,
        actor_name=admin_user.full_name,
        target_user_id=req.user_id,
        details={
            "driver_id": req.user_id,
            "rejection_reason": clean_reason,
            "status": "rejected",
        },
    )

    db.commit()
    db.refresh(req)
    return req
