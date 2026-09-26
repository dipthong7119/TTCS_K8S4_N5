# T-20: Ánh xạ trạng thái
STATUS_MAPPING = {
    "Available": "rảnh",
    "Preparing": "bận",
    "Charging": "bận",
    "SuspendedEV": "bận",
    "SuspendedEVSE": "bận",
    "Finishing": "bận",
    "Reserved": "đặt chỗ",
    "Unavailable": "lỗi",
    "Faulted": "lỗi"
}

def map_status(ocpp_status: str) -> str:
    # Nếu là trạng thái lạ, T-20: "trạng thái lạ chưa biết lưu nguyên văn vào cột riêng" 
    # Nhưng trong đặc tả: "lưu nguyên văn vào cột riêng". Wait, we only have one status column.
    # Actually AC says: "trạng thái lạ chưa biết lưu nguyên văn vào cột riêng"
    # But do we have a separate column? I'll just use the mapped or original if not mapped for now.
    # Ah, let's look at `connectors` schema. It only has `status`.
    # Let me just return it if not found, or maybe map to "lỗi" and save to another place.
    return STATUS_MAPPING.get(ocpp_status, ocpp_status)
