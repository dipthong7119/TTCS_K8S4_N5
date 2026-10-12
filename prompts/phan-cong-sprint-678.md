# Phân công SCRUM Sprint 678

**Quy mô:** 19 work item · 63 SP · SCRUM-76 → SCRUM-98
**Nguyên tắc chia:** mỗi người sở hữu **trọn vẹn một nhóm story liên quan** (cùng epic), để làm xong không phải chờ ai và không sửa chung code với ai. Scrum Master (Trịnh Thanh Tùng) nhận nhiều việc nhất.

---

## 1. Tổng quan tải công việc

| Thành viên | Vai trò | Story phụ trách | Tổng SP |
|---|---|---|---|
| **Trịnh Thanh Tùng** | Scrum Master (làm thêm BE) | 80, 81, 82, 83, 97 | **17** |
| Nguyễn Lâm Tùng | BE | 78, 79, 96 | 11 |
| Tạ Như Vinh | BE | 86, 87, 88 | 9 |
| Hoàng Văn Đức | BE | 90, 91, 92 | 9 |
| Ngô Quang Tùng | BE | 76, 77 | 8 |
| Hoàng Văn Tân | BE | 84, 85 | 8 |
| Vy Hoàng Tú | FE | 98 + toàn bộ subtask FE epic *Ứng dụng tài xế* và *Phân bổ công suất* | 1 (+ subtask FE) |
| Phạm Văn Tuấn | FE | toàn bộ subtask FE epic *Đặt chỗ trụ sạc* và *Giám sát vận hành* | subtask FE |
| Đặng Ngọc Đại | FE | toàn bộ subtask FE epic *Đối soát và chia doanh thu* | subtask FE |

> Tổng SP của story: 17 + 11 + 9 + 9 + 8 + 8 + 1 = **63 SP** ✔
> SP được tính cho người sở hữu story (BE). Các subtask `[FE]` của story do FE phụ trách epic đó làm, không tính thêm SP.

---

## 2. Chi tiết theo từng người

### Trịnh Thanh Tùng (Scrum Master) — 17 SP
Sở hữu **nguyên epic Phân bổ công suất** (khép kín, không phụ thuộc epic khác) + 1 story nhỏ.

| Key | Công việc | SP |
|---|---|---|
| SCRUM-80 | Chủ trạm đặt hạn mức công suất cho trạm | 3 |
| SCRUM-81 | Tổng công suất cấp cho các trụ đang sạc không vượt hạn mức trạm | 5 |
| SCRUM-82 | Công suất được chia lại khi có xe vào hoặc rời trạm | 5 |
| SCRUM-83 | Chủ trạm đặt hạn mức công suất theo khung giờ | 3 |
| SCRUM-97 | Tài xế nhận thông báo khi phiên kết thúc hoặc bị dừng | 1 |

- Làm tuần tự theo thứ tự: **80 → 83 → 81 → 82** (80 là dữ liệu nền cho 81, 82, 83).
- Subtask `[FE]` của epic này giao cho **Vy Hoàng Tú**.

### Ngô Quang Tùng (BE) — 8 SP
Epic **Đặt chỗ trụ sạc** — phần tạo đặt chỗ.

| Key | Công việc | SP |
|---|---|---|
| SCRUM-76 | Tài xế đặt chỗ một trụ trong khoảng thời gian | 5 |
| SCRUM-77 | Hai tài xế đặt cùng trụ cùng lúc thì chỉ một người thành công | 3 |

### Nguyễn Lâm Tùng (BE) — 11 SP
Epic **Đặt chỗ trụ sạc** — phần huỷ/giữ chỗ + tìm trạm.

| Key | Công việc | SP |
|---|---|---|
| SCRUM-78 | Giữ chỗ quá giờ không tới thì bị huỷ và tính phí | 3 |
| SCRUM-79 | Tài xế huỷ chỗ đã đặt và trụ mở lại cho người khác | 3 |
| SCRUM-96 | Tài xế tìm trạm gần và thấy đầu nối nào đang rảnh | 5 |

### Hoàng Văn Tân (BE) — 8 SP
Epic **Đối soát và chia doanh thu** — phần tính toán đối soát.

| Key | Công việc | SP |
|---|---|---|
| SCRUM-84 | Chủ trạm xem doanh thu và sản lượng kWh theo kỳ, theo từng trụ | 3 |
| SCRUM-85 | Kế toán đối soát tổng kWh đã cấp với tổng tiền đã thu | 5 |

### Tạ Như Vinh (BE) — 9 SP
Epic **Đối soát và chia doanh thu** — phần chia doanh thu, chốt kỳ, xuất báo cáo.

| Key | Công việc | SP |
|---|---|---|
| SCRUM-86 | Chia doanh thu cho đối tác theo tỉ lệ hợp đồng | 3 |
| SCRUM-87 | Kỳ đối soát được chốt và khoá | 3 |
| SCRUM-88 | Xuất báo cáo doanh thu và đối soát ra tệp CSV | 3 |

### Hoàng Văn Đức (BE) — 9 SP
Epic **Giám sát vận hành** (khép kín).

| Key | Công việc | SP |
|---|---|---|
| SCRUM-90 | Cảnh báo khi trụ ngoại tuyến quá lâu hoặc báo lỗi liên tục | 3 |
| SCRUM-91 | Nhật ký thao tác trên giao dịch ví truy được ai làm gì | 3 |
| SCRUM-92 | Tài xế yêu cầu xoá dữ liệu cá nhân và lịch sử di chuyển | 3 |

### Frontend

| Thành viên | Epic phụ trách (subtask `[FE]`) | Ghi chú |
|---|---|---|
| **Phạm Văn Tuấn** | Đặt chỗ trụ sạc (76–79) + Giám sát vận hành (90–92) | Làm việc với Ngô Quang Tùng, Nguyễn Lâm Tùng, Hoàng Văn Đức |
| **Vy Hoàng Tú** | Ứng dụng tài xế (96, 97, 98) + Phân bổ công suất (80–83) | Sở hữu trọn **SCRUM-98** (1 SP, đã gán sẵn trên Jira); gồm SCRUM-241, 242 của SCRUM-96 |
| **Đặng Ngọc Đại** | Đối soát và chia doanh thu (84–88) | Gồm SCRUM-231 của SCRUM-85; làm việc với Hoàng Văn Tân, Tạ Như Vinh |

---

## 3. Cách tránh "dính nhau"

1. **Chia theo epic, không chia theo lớp kỹ thuật**: mỗi cụm story nằm trọn trong tay một người/cặp BE–FE, không ai phải chờ code của người ngoài cụm.
2. **Chốt API contract ngày đầu sprint** (endpoint, request/response mẫu). FE làm trên mock theo contract, không chờ BE xong. Trịnh Thanh Tùng chốt và duy trì bản contract chung.
3. **Dữ liệu dùng chung** (trạm, trụ, đầu nối, phiên sạc): thống nhất schema ngay ngày 1; ai cần thêm field thì báo trong kênh nhóm trước khi sửa, không tự đổi bảng/entity dùng chung.
4. **Mỗi người một nhánh riêng theo story** (`feature/SCRUM-xx-...`), không làm chung một nhánh; merge vào nhánh chính qua PR.
5. **Hai điểm phụ thuộc cần lưu ý**:
   - Epic *Phân bổ công suất*: làm **SCRUM-80 trước** vì 81, 82, 83 dùng dữ liệu hạn mức.
   - Epic *Đối soát*: **SCRUM-88 (xuất CSV)** của Vinh dùng số liệu từ Tân (84, 85) → hai người thống nhất định dạng dữ liệu tổng hợp sớm, Vinh làm 86, 87 trước rồi mới làm 88.

---

## 4. Review chéo & kiểm thử (các subtask `[QA]`)

Vòng review để mỗi người review đúng một người, không ai phải đợi nhiều người:

| Người review / kiểm thử | Review phần của |
|---|---|
| Nguyễn Lâm Tùng | Ngô Quang Tùng |
| Hoàng Văn Tân | Nguyễn Lâm Tùng |
| Tạ Như Vinh | Hoàng Văn Tân |
| Hoàng Văn Đức | Tạ Như Vinh |
| Ngô Quang Tùng | Hoàng Văn Đức |
| Tạ Như Vinh + Hoàng Văn Tân | Trịnh Thanh Tùng (chia đôi: Vinh review 80, 83, 97; Tân review 81, 82) |
| Trịnh Thanh Tùng | Phần FE của cả ba bạn FE (review tổng, mỗi PR FE cần thêm 1 FE khác xem chéo) |

Subtask `[QA]` của mỗi story do **người review tương ứng** thực hiện, không phải người viết code.

---

## 5. Gợi ý lịch làm việc

| Giai đoạn | Việc cần chốt |
|---|---|
| Ngày 1 | Họp ngắn chốt API contract + schema dùng chung; mỗi người nhận story và tạo nhánh |
| Giữa sprint | Các story lớn (76, 81, 82, 85, 96) đã có API chạy được cho FE nối thật |
| Cuối sprint | Review chéo, kiểm thử `[QA]`, sửa lỗi, demo |

> Nếu có người quá tải hoặc nghỉ, chuyển story nhỏ (3 SP) trong cùng epic cho người cùng cụm để giữ nguyên ranh giới phụ thuộc.
