# Kết quả rà soát T-23 — Cây trạm, trụ và đầu nối trong một truy vấn

**Trạng thái:** Đạt tiêu chí cục bộ; chờ tích hợp vào CI

- Bổ sung kiểm tra với 50 trụ và 200 đầu nối; API trả đủ cây ba tầng bằng đúng một câu truy vấn và dưới 200 ms trên SQLite in-memory.
- Test phân quyền chủ trạm hiện có xác nhận chỉ nhận dữ liệu thuộc sở hữu.
- Chưa có phép đo trên PostgreSQL/staging. Story S-11 vẫn cần xác nhận luồng 20 trụ trực tiếp.
