# SCRUM-65 / S-32 — Trịnh Thanh Tùng

Ngày thực hiện: **09/10/2026**, UTC+7. Nhánh kiểm tra và bàn giao: `TRINH-TUNG`,
cập nhật từ `origin/sprint-3` tại `58a4c07` trước khi thêm SCRUM-65.

Đã chuẩn bị **24 ca có đáp án tính tay** và bộ test tự động đối chiếu với hàm
tính tiền hiện tại. Cập nhật **12/10/2026**: 20 ca tính tiền đạt, còn bốn ca
phí chiếm trụ 21–24 chờ SCRUM-61/204. SCRUM-65 chưa đủ điều kiện chuyển Done.
SCRUM-65-20 dùng các phiên bản biểu giá theo ngày và đạt đáp án 36.000 đồng.

## Phần đã thực hiện

| File | Nội dung |
| --- | --- |
| `backend/tests/scrum65_pricing_cases.json` | Đầu vào, đáp án cố định và phép tính độc lập cho 24 ca; tên người lập Trịnh Thanh Tùng (cùng Codex), ngày 09/10/2026, người review Tạ Như Vinh chưa duyệt. |
| `backend/tests/unit/test_scrum65_pricing.py` | Test theo bảng; so từng đoạn, mốc giờ, kWh, đơn giá và tiền nguyên đồng. Khi sai, báo mã ca, số đoạn và chênh lệch thực tế − đáp án. |
| `huongdan/kiem_thu_SCRUM-65.md` | Bảng tính tay dễ đọc, lệnh chạy lại, phạm vi đã kiểm chứng và cách bật các ca đang chờ. |

Các ca gồm một khung, cắt mốc 06:00/17:00/22:00, đầu/cuối đúng ranh giới,
nửa đêm, dữ liệu UTC nhưng chia ngày theo trạm, phiên 26 giờ, nội suy số đo
thưa, Wh/kWh, không tiêu thụ và làm tròn tới đồng ở từng đoạn. Các ca 13/14/19
phân biệt được làm tròn mỗi số đo, làm tròn tổng phiên và làm tròn từng đoạn.

Không sửa thuật toán, API, model hoặc migration trong task này. Test đọc đáp án
từ tệp riêng, không sinh đáp án bằng thuật toán đang được kiểm tra.

## Bằng chứng local

| Kiểm tra | Kết quả |
| --- | --- |
| Pytest riêng SCRUM-65 | **23 passed, 4 skipped**: 20 ca tiền, test metadata/phạm vi và test thông báo khi sai một đồng. |
| Hồi quy backend cho SCRUM-64/66/72/209/210 và luồng tính tiền, ví, StopTransaction | **169 passed, 4 skipped**, 13 cảnh báo; bốn ca bỏ qua là SCRUM65-21–24. |
| JavaScript giao diện | **89/89 đạt**, gồm trạng thái ví thấp và mở hóa đơn từ API. |
| Kiểm tra asset/frontend | **21 passed**. |
| Ruff cho mã backend liên quan và Mypy toàn `app` | Đạt; Mypy kiểm tra 60 file nguồn. |
| `git diff --check` | Đạt sau cập nhật. |

Môi trường kiểm tra hiện tại: Windows, Python **3.14.2**, pytest **9.1.1** trong
`.venv` của repo. Đã chạy các nhóm backend liên quan và kiểm tra giao diện; chưa
chạy bộ CI đầy đủ, Docker/PostgreSQL hoặc nghiệm thu staging trong lượt rà soát này.
CI hiện thu thập `backend/tests`, nên không cần thay workflow để chạy file mới.

Log local được Git ignore tại `outputs/sprint3-ci/scrum65-ci-pytest.log`,
`scrum65-ci-junit.xml`, `scrum65-coverage.xml` và `scrum65-ci-frontend.log` trong
cùng thư mục. GitHub CI chạy lại bằng Python 3.11 sau khi push, gồm build image,
Docker/PostgreSQL và kịch bản 20 trụ. Kết quả workflow xem trên GitHub Actions
của commit được push; các con số trong bảng trên là bằng chứng local trước commit.

Đã kiểm tra cấu hình CI/CD: push lên `TRINH-TUNG` chạy CI; workflow CD chỉ nhận
push từ `main`, `master`, `sprint-3`, và job triển khai staging chỉ chạy từ
`main`/`master` sau khi CI thành công. Task này không thay đổi workflow triển khai.

Lệnh và bảng chi tiết: [Kiểm thử SCRUM-65](../huongdan/kiem_thu_SCRUM-65.md).

## Phần còn chờ

| Ca | Đáp án | Phụ thuộc còn thiếu |
| --- | ---: | --- |
| SCRUM65-21/22 | 10.000 đồng mỗi ca, gồm 2.000 phí chiếm trụ | SCRUM-61/204: phí theo phút, ân hạn và thời điểm rút súng. |
| SCRUM65-23/24 | 8.000 đồng mỗi ca, phí chiếm trụ 0 | Cùng phụ thuộc phí chiếm trụ; chưa coi tổng tiền điện khớp là đã kiểm tra ân hạn. |

Bốn ca 21–24 vẫn skip do phí chiếm trụ chưa được nối với dữ liệu thời điểm rút
súng và ân hạn. Khi SCRUM-61/204 có đầu vào, nối adapter và kiểm tra riêng tiền
phí/số phút rồi chạy lại.

Tại thời điểm lập bằng chứng local, chưa có review của Tạ Như Vinh, kết quả GitHub
CI cho thay đổi này hay nghiệm thu staging. Bộ dữ liệu có thể bàn giao cho
SCRUM-209/210, nhưng báo cáo này không
thay thế kiểm thử tích hợp nhiều khung giờ hoặc đối soát phiên thực tế.
