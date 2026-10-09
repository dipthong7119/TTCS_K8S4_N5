"""Danh sách cấu hình OCPP được phép đổi từ xa."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigurationKey:
    """Giới hạn và mô tả của một khóa cấu hình."""

    value_type: type[int]
    minimum: int
    maximum: int
    description: str


# Các khoảng này giữ MeterValues luôn hoạt động và tránh nhịp tim quá dày.
CONFIGURATION_KEYS: dict[str, ConfigurationKey] = {
    "HeartbeatInterval": ConfigurationKey(
        int, 30, 3600, "Khoảng nhịp tim, giây"
    ),
    "MeterValueSampleInterval": ConfigurationKey(
        int, 5, 900, "Chu kỳ gửi số đo, giây"
    ),
}

_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")


class ConfigurationValidationError(ValueError):
    """Lỗi thuần khi kiểm tra khóa hoặc giá trị cấu hình."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def validate_change(key: str, raw_value: object) -> int:
    """Kiểm tra và chuẩn hóa một giá trị cấu hình."""
    spec = CONFIGURATION_KEYS.get(key)
    if spec is None:
        raise ConfigurationValidationError("unknown_key", "Khóa cấu hình không được phép")

    if isinstance(raw_value, bool):
        raise ConfigurationValidationError("invalid_integer", "Giá trị phải là số nguyên")
    if isinstance(raw_value, int):
        value = raw_value
    elif isinstance(raw_value, str) and _INTEGER_PATTERN.fullmatch(raw_value.strip()):
        value = int(raw_value.strip())
    else:
        raise ConfigurationValidationError("invalid_integer", "Giá trị phải là số nguyên")

    if not spec.minimum <= value <= spec.maximum:
        raise ConfigurationValidationError(
            "out_of_range",
            f"Giá trị phải trong khoảng {spec.minimum}..{spec.maximum}",
        )
    return value
