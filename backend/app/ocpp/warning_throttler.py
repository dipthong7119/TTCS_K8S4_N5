import time
from collections.abc import Callable


class WarningThrottler:
    """
    Gom nhóm cảnh báo để không spam log khi trụ gửi liên tục sự kiện.
    Sử dụng khoá (mã trụ, thông tin thêm) để theo dõi khoảng thời gian.
    """

    def __init__(self, get_time: Callable[[], float] = time.time):
        # dictionary lưu thời điểm cảnh báo gần nhất, key là tuple(str, int)
        self._last_warn_time: dict[tuple[str, int], float] = {}
        self._get_time = get_time

    def should_warn(self, charge_point_code: str, connector_id: int, interval_seconds: int) -> bool:
        """
        Kiểm tra xem có nên ghi log cảnh báo không dựa trên khoảng thời gian gom (interval_seconds).
        Đồng thời dọn dẹp bộ nhớ các khoá đã cũ.
        """
        now = self._get_time()
        key = (charge_point_code, connector_id)

        last_warn = self._last_warn_time.get(key)
        if last_warn is None or now - last_warn >= interval_seconds:
            self._last_warn_time[key] = now
            # Dọn dẹp khoá cũ sau khi đã quyết định (tránh xoá key hiện tại trước khi kiểm tra)
            self._cleanup(now, interval_seconds, exclude_key=key)
            return True
        return False


    def _cleanup(self, now: float, interval_seconds: int, exclude_key: tuple | None = None):
        """Xoá các khoá đã quá thời gian interval_seconds khỏi bộ nhớ tiến trình."""
        # Dùng list(keys()) để tạo bản sao khoá, tránh lỗi "dictionary changed size during iteration"
        for k in list(self._last_warn_time.keys()):
            if k == exclude_key:
                continue
            if now - self._last_warn_time[k] >= interval_seconds:
                del self._last_warn_time[k]

# Instance chung (singleton pattern) cho toàn ứng dụng
unknown_connector_throttler = WarningThrottler()
