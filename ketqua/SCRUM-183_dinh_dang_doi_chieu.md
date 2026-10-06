# ĐẶC TẢ ĐỊNH DẠNG DỮ LIỆU ĐỐI CHIẾU NĂNG LƯỢNG KWH (SCRUM-183 / 184)

**Task**: SCRUM-183 (Đức - Thu thập và đối chiếu kWh) & SCRUM-184 (Tuấn - Xuất bảng đối chiếu) & SCRUM-182 (Tú - Kịch bản 20 trụ ảo)
**Phụ trách thiết kế**: Hoàng Văn Đức (Backend)
**Trạng thái**: Đã thống nhất định dạng JSON và hoàn tất công cụ đối chiếu lõi tại `backend/app/services/kwh_reconciliation.py`.

---

## 1. Mục tiêu

Đáp ứng tiêu chí nghiệm thu của **S-21** (Phiên đang dở được khôi phục đúng khi trụ nối lại) và **E-04** (Kết nối OCPP và phiên sạc):
* 20 trụ ảo chạy 20 phiên sạc độc lập.
* Trong quá trình sạc, mỗi trụ bị ngắt–nối ngẫu nhiên từ 1 đến 3 lần.
* Khi kết thúc phiên, so sánh số kWh do hệ thống CSMS tính toán (`system_kwh`) với số kWh do Simulator báo cáo (`simulator_kwh`).
* Sai số chấp nhận được: $\le 0.001$ kWh (chênh lệch làm tròn Wh sang kWh).

---

## 2. Cấu trúc JSON kết quả đối chiếu chuẩn

File mẫu được lưu tại: [kwh_reconciliation_sample.json](kwh_reconciliation_sample.json).
Đây là dữ liệu mẫu cho kiểm thử và bàn giao định dạng, chưa phải kết quả
thu thập từ một lượt chạy 20 trụ/ngắt nối thật. Module hiện nhận hai tập dữ
liệu đầu vào; chưa tự gọi API/DB hoặc chạy simulator để thu thập.

```json
{
  "metadata": {
    "title": "Bảng dữ liệu mẫu đối chiếu kWh hệ thống CSMS vs Simulator (20 trụ ảo)",
    "task": "SCRUM-183 (Đức) & SCRUM-184 (Tuấn) & SCRUM-182 (Tú)",
    "generated_at": "2026-10-06T11:00:00Z",
    "total_charge_points": 20,
    "tolerance_kwh": 0.001
  },
  "summary": {
    "total_sessions": 20,
    "matched_sessions": 20,
    "mismatched_sessions": 0,
    "match_percentage": 100.0,
    "total_system_kwh": 372.45,
    "total_simulator_kwh": 372.45,
    "total_difference_kwh": 0.0,
    "verdict": "PASSED"
  },
  "sessions": [
    {
      "session_id": 1001,
      "charge_point_code": "CP01",
      "connector_id": 1,
      "meter_start_wh": 12500,
      "meter_stop_wh": 28700,
      "disconnect_count": 2,
      "system_kwh": 16.200,
      "simulator_kwh": 16.200,
      "difference_kwh": 0.0,
      "status": "MATCH",
      "notes": "Trụ ngắt nối 2 lần giữa phiên, khôi phục thành công"
    }
  ]
}
```

---

## 3. Các trường thông tin chi tiết của mỗi phiên (`sessions[]`)

| Tên trường | Kiểu dữ liệu | Ý nghĩa | Ví dụ |
| :--- | :--- | :--- | :--- |
| `session_id` | `int` | Mã định danh phiên sạc (PK bảng `charging_sessions`) | `1001` |
| `charge_point_code` | `string` | Mã định danh trụ sạc | `"CP01"` |
| `connector_id` | `int` | Số thứ tự đầu nối | `1` |
| `meter_start_wh` | `int` | Số đo đồng hồ lúc bắt đầu (Wh) | `12500` |
| `meter_stop_wh` | `int` | Số đo đồng hồ lúc kết thúc (Wh) | `28700` |
| `disconnect_count` | `int` | Số lần ngắt-nối ngẫu nhiên trong phiên | `2` |
| `system_kwh` | `float` | Năng lượng do CSMS ghi nhận và tính toán (kWh) | `16.200` |
| `simulator_kwh` | `float` | Năng lượng do thiết bị giả lập ghi nhận (kWh) | `16.200` |
| `difference_kwh` | `float` | Chênh lệch tuyệt đối: `abs(system_kwh - simulator_kwh)` | `0.000` |
| `status` | `string` | Trạng thái đối chiếu: `MATCH`, `MISMATCH`, `MISSING_IN_SYSTEM`, `MISSING_IN_SIMULATOR` | `"MATCH"` |
| `notes` | `string` | Ghi chú chi tiết kết quả chạy | `"Khôi phục phiên thành công"` |

---

## 4. Hướng dẫn tích hợp cho các thành viên

1. **Cho Vy Hoàng Tú (SCRUM-182 - Kịch bản 20 trụ)**:
   - Khi viết kịch bản tự động ngắt–nối 20 trụ, xuất kết quả chạy của 20 phiên theo đúng định dạng các trường `session_id`, `charge_point_code`, `meter_start_wh`, `meter_stop_wh`, `simulator_kwh`, `disconnect_count`.
2. **Cho Phạm Văn Tuấn (SCRUM-184 - Xuất bảng đối chiếu)**:
   - Tuấn có thể sử dụng trực tiếp hàm `export_markdown_table()` trong module `backend/app/services/kwh_reconciliation.py` hoặc đọc file JSON mẫu `ketqua/kwh_reconciliation_sample.json` để dựng template xuất báo cáo (HTML/Markdown) mà không cần chờ chạy kịch bản thật.
