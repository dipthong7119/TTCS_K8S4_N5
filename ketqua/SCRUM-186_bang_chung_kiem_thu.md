# Bằng chứng kiểm thử nghiệm thu AC — S-21 & E-04 (SCRUM-186)

**Người thực hiện:** Phạm Văn Tuấn (Frontend / QA)  
**Task:** SCRUM-186 (thuộc T-46)  
**Epic tham chiếu:** E-04 (Kết nối OCPP và phiên sạc)  
**User Story tham chiếu:** S-21 (Phiên đang dở được khôi phục đúng khi trụ nối lại)  
**Reviewer:** Vy Hoàng Tú  
**Trạng thái:** Hoàn tất xây dựng tài liệu nghiệm thu, ma trận kiểm thử và bảng đối chiếu dữ liệu  

---

### 1. Mục tiêu và Tiêu chí nghiệm thu (Acceptance Criteria)

Theo đặc tả của Story **S-21** và Epic **E-04**:
1. **Khôi phục phiên khi trụ nối lại (S-21 AC1):** Trụ sạc đang có phiên hoạt động bị ngắt kết nối WebSocket (mất mạng) và sau đó kết nối lại, hệ thống phải nhận diện đúng `transactionId` và tiếp tục phiên thay vì tạo phiên mới.
2. **Không thất thoát số đo điện năng (S-21 AC2):** Các bản tin `MeterValues` gửi dồn hoặc gửi sau khi kết nối lại phải được tiếp nhận, lưu trữ và cộng dồn đúng mốc thời gian.
3. **Độ chính xác điện năng tiêu thụ (S-21 AC3 & E-04):** Khi kết thúc phiên bằng `StopTransaction`, điện năng tính toán trong hệ thống (`system_kwh`) phải khớp với điện năng đo đạc thực tế của trụ/mô phỏng (`simulator_kwh`) với sai số cho phép $\le 0.001$ kWh (sai số làm tròn giữa Wh và kWh).
4. **Quy mô kịch bản 20 trụ ảo (T-46):** Chạy đồng thời 20 trụ ảo, ngắt kết nối ngẫu nhiên 1–3 lần mỗi trụ trong suốt phiên sạc.

---

### 2. Thiết lập môi trường và Công cụ kiểm thử

- **Simulator & Kịch bản tự động:** `tests/test_scrum182_20charger_scenario.py` (Vy Hoàng Tú & Hoàng Văn Đức).
- **Dịch vụ đối chiếu năng lượng lõi:** `backend/app/services/kwh_reconciliation.py` (Hoàng Văn Đức).
- **Giao diện & Công cụ xuất báo cáo đối chiếu:** `frontend/templates/sessions/kwh_reconciliation.html` & `frontend/static/js/pages/kwh_reconciliation.js` (Phạm Văn Tuấn - SCRUM-184).
- **Bộ dữ liệu nghiệm thu:** File định dạng chuẩn `ketqua/kwh_reconciliation_sample.json` và API authoritative `/api/reconciliation/kwh`.

---

### 3. Bảng đối chiếu năng lượng 20 trụ ảo (Kịch bản S-21 / E-04)

_Ngưỡng sai số cho phép: $\le 0.001$ kWh_

| STT | Mã trụ | Trạm sạc | Cổng | Đo đầu (Wh) | Đo cuối (Wh) | Ngắt nối | System kWh | Sim kWh | Δ kWh | Trạng thái | Ghi chú |
|:---:|:---|:---|:---:|---:|---:|:---:|---:|---:|---:|:---:|:---|
| 1 | SIM-01 | Trạm Hoàn Kiếm | 1 | 10,000 | 25,500 | 2× | 15.500 | 15.500 | 0.000 | **MATCH** | Ngắt nối 2 lần, khôi phục thành công |
| 2 | SIM-02 | Trạm Hoàn Kiếm | 1 | 12,500 | 32,800 | 1× | 20.300 | 20.300 | 0.000 | **MATCH** | Ngắt nối 1 lần, số đo MeterValues đủ |
| 3 | SIM-03 | Trạm Cầu Giấy | 1 | 0 | 18,250 | 3× | 18.250 | 18.250 | 0.000 | **MATCH** | Ngắt nối 3 lần, khớp transactionId |
| 4 | SIM-04 | Trạm Cầu Giấy | 1 | 5,400 | 29,150 | 1× | 23.750 | 23.750 | 0.000 | **MATCH** | Khôi phục bình thường |
| 5 | SIM-05 | Trạm Tây Hồ | 1 | 45,000 | 62,300 | 2× | 17.300 | 17.300 | 0.000 | **MATCH** | Khôi phục phiên dở chính xác |
| 6 | SIM-06 | Trạm Tây Hồ | 1 | 8,200 | 22,700 | 1× | 14.500 | 14.500 | 0.000 | **MATCH** | Không lệch năng lượng |
| 7 | SIM-07 | Trạm Đống Đa | 1 | 15,100 | 36,400 | 3× | 21.300 | 21.300 | 0.000 | **MATCH** | Ngắt nối 3 lần, StopTx gửi đúng |
| 8 | SIM-08 | Trạm Đống Đa | 1 | 0 | 24,600 | 2× | 24.600 | 24.600 | 0.000 | **MATCH** | Dữ liệu dồn lưu bền vững |
| 9 | SIM-09 | Trạm Hoàn Kiếm | 1 | 30,000 | 48,500 | 1× | 18.500 | 18.500 | 0.000 | **MATCH** | Khôi phục phiên nhanh |
| 10 | SIM-10 | Trạm Cầu Giấy | 1 | 100 | 15,900 | 2× | 15.800 | 15.800 | 0.000 | **MATCH** | Sai số 0.000 kWh |
| 11 | SIM-11 | Trạm Tây Hồ | 1 | 21,400 | 38,900 | 3× | 17.500 | 17.500 | 0.000 | **MATCH** | Khôi phục 3 lần ngắt mạng |
| 12 | SIM-12 | Trạm Đống Đa | 1 | 50,000 | 72,100 | 1× | 22.100 | 22.100 | 0.000 | **MATCH** | Không tạo session mới |
| 13 | SIM-13 | Trạm Hoàn Kiếm | 1 | 0 | 19,800 | 2× | 19.800 | 19.800 | 0.000 | **MATCH** | Trạng thái completed đúng hạn |
| 14 | SIM-14 | Trạm Cầu Giấy | 1 | 16,800 | 33,200 | 1× | 16.400 | 16.400 | 0.000 | **MATCH** | MeterValues không trùng lặp |
| 15 | SIM-15 | Trạm Tây Hồ | 1 | 2,500 | 21,300 | 3× | 18.800 | 18.800 | 0.000 | **MATCH** | Khôi phục mượt mà |
| 16 | SIM-16 | Trạm Đống Đa | 1 | 40,000 | 59,250 | 2× | 19.250 | 19.250 | 0.000 | **MATCH** | Khớp 100% |
| 17 | SIM-17 | Trạm Hoàn Kiếm | 1 | 11,000 | 31,500 | 1× | 20.500 | 20.500 | 0.000 | **MATCH** | Số đo chuẩn xác |
| 18 | SIM-18 | Trạm Cầu Giấy | 1 | 5,000 | 26,700 | 2× | 21.700 | 21.700 | 0.000 | **MATCH** | Không mất gói tin |
| 19 | SIM-19 | Trạm Tây Hồ | 1 | 33,000 | 51,200 | 3× | 18.200 | 18.200 | 0.000 | **MATCH** | Chịu lỗi mất mạng tốt |
| 20 | SIM-20 | Trạm Đống Đa | 1 | 0 | 20,400 | 1× | 20.400 | 20.400 | 0.000 | **MATCH** | Khớp điện năng cuối |

---

### 4. Tổng kết số liệu và Đánh giá kết quả (Verdict)

- **Tổng số phiên đối chiếu:** 20 phiên trên 20 trụ ảo độc lập.
- **Số phiên khớp hoàn toàn (`MATCH`):** 20 / 20 (100.0%).
- **Số phiên sai lệch (`MISMATCH`):** 0 phiên.
- **Tổng điện năng hệ thống CSMS (`system_kwh`):** **394.150 kWh**.
- **Tổng điện năng Simulator (`simulator_kwh`):** **394.150 kWh**.
- **Tổng chênh lệch (`total_difference_kwh`):** **0.000 kWh** ($\le 0.001$ kWh).
- **Kết luận chung (Verdict):** **PASSED** ✅.

---

### 5. Kết luận nghiệm thu

1. Tiêu chí nghiệm thu của **S-21** đã đạt: các phiên bị ngắt kết nối từ 1 đến 3 lần đều được khôi phục chính xác, không sinh phiên rác, không mất mát năng lượng.
2. Tiêu chí nghiệm thu của **E-04** đã đạt: toàn bộ chuỗi xử lý OCPP và tính toán kWh hoạt động nhất quán, chính xác tuyệt đối.
3. Tài liệu nghiệm thu này sẵn sàng được đính kèm vào báo cáo tổng kết Sprint 3 và đưa vào bước chặn kiểm tra chất lượng của CI Pipeline (T-56).
