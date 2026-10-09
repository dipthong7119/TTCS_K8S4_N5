# SCRUM-65 / S-32 — Trịnh Thanh Tùng

Ngày thực hiện: **09/10/2026**, UTC+7. Nhánh kiểm tra và bàn giao: `TRINH-TUNG`,
cập nhật từ `origin/sprint-3` tại `58a4c07` trước khi thêm SCRUM-65.

Đã chuẩn bị **24 ca có đáp án tính tay** và bộ test tự động đối chiếu với hàm
tính tiền hiện tại. **19 ca tính tiền đã đạt; 5 ca còn chờ phần nghiệp vụ phụ
thuộc. SCRUM-65 chưa đủ điều kiện chuyển Done.**

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
| Pytest riêng SCRUM-65 | **21 passed, 5 skipped**: 19 ca tiền, 1 test metadata/phạm vi, 1 test thông báo khi sai một đồng. |
| Pytest cùng StopTransaction và tính kWh | **44 passed, 5 skipped**, 7 cảnh báo từ bộ test/phụ thuộc hiện có. |
| Toàn bộ pytest theo bước CI, tách kịch bản Docker 20 trụ | **547 passed, 5 skipped**, 64 cảnh báo; 58,94 giây. Chỉ năm ca SCRUM-65 chờ phụ thuộc bị bỏ qua. |
| JavaScript theo bước CI | **81/81 đạt**, không lỗi hoặc bỏ qua. |
| Ruff toàn bộ app, tests, Alembic và scripts | Đạt. |
| Mypy | Đạt, 48 file nguồn. |
| `pip_audit --local` | Không phát hiện lỗ hổng đã biết. |
| `git diff --check` | Đạt tại thời điểm kiểm tra. |

Môi trường kiểm tra: Windows, Python **3.14.2**, pytest **9.1.1** trong `.venv`
của repo. Đã chạy bộ pytest theo bước CI; chưa chạy bước Docker/PostgreSQL local
cho task này vì Docker Engine chưa hoạt động, chưa nghiệm thu staging.
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
| SCRUM65-20 | 36.000 đồng | SCRUM-64/206: chọn phiên bản biểu giá theo từng ngày; pricing hiện chỉ nhận một bộ bands, billing chọn giá lúc bắt đầu. |
| SCRUM65-21/22 | 10.000 đồng mỗi ca, gồm 2.000 phí chiếm trụ | SCRUM-61/204: phí theo phút, ân hạn và thời điểm rút súng. |
| SCRUM65-23/24 | 8.000 đồng mỗi ca, phí chiếm trụ 0 | Cùng phụ thuộc phí chiếm trụ; chưa coi tổng tiền điện khớp là đã kiểm tra ân hạn. |

Năm ca được đánh dấu skip có lý do rõ ràng, không được tính là pass. Bảng ca đã
đủ các nhóm theo S-32, nhưng AC “mọi ca khớp đáp án” chưa đạt vì năm ca chưa chạy.
Khi có hàm hỗ trợ, nối adapter thật và kiểm tra phí/số phút rồi chạy lại.

Tại thời điểm lập bằng chứng local, chưa có review của Tạ Như Vinh, kết quả GitHub
CI cho thay đổi này hay nghiệm thu staging. Bộ dữ liệu có thể bàn giao cho
SCRUM-209/210, nhưng báo cáo này không
thay thế kiểm thử tích hợp nhiều khung giờ hoặc đối soát phiên thực tế.
