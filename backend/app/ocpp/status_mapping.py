"""
Module ánh xạ trạng thái OCPP sang trạng thái nội bộ.
Đảm bảo tính thuần tuý (pure function), không phụ thuộc database hay mạng.
"""

from enum import Enum


class InternalStatus(str, Enum):
    IDLE = "rảnh"
    BUSY = "bận"
    RESERVED = "đặt chỗ"
    FAULTED = "lỗi"


def map_ocpp_status(ocpp_status: str) -> InternalStatus:
    """
    Ánh xạ 9 trạng thái OCPP 1.6 sang 4 trạng thái nội bộ.
    Các trạng thái lạ sẽ mặc định chuyển thành LỖI để đảm bảo an toàn.
    """
    if ocpp_status == "Available":
        return InternalStatus.IDLE
    elif ocpp_status in {
        "Preparing",
        "Charging",
        "SuspendedEV",
        "SuspendedEVSE",
        "Finishing",
    }:
        return InternalStatus.BUSY
    elif ocpp_status == "Reserved":
        return InternalStatus.RESERVED
    elif ocpp_status in {"Unavailable", "Faulted"}:
        return InternalStatus.FAULTED
    else:
        # Nếu gửi trạng thái lạ, ta fallback về lỗi (hoặc rảnh tuỳ business, nhưng lỗi thì an toàn nhất để tránh xe mới vào cắm sạc)
        return InternalStatus.FAULTED
