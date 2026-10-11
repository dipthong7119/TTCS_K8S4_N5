"""Trạng thái phiên chưa có StopTransaction và vẫn được theo dõi."""

OPEN_SESSION_STATUSES: tuple[str, ...] = ("active", "needs_review", "anomaly")
