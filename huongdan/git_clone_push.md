# Clone, đồng bộ và push dự án CSMS

Tài liệu này gom nội dung Git trước đây ở `HD.txt` và `hướng dẫn clone push.txt`.

## Clone dự án

```powershell
git clone https://github.com/dipthong7119/TTCS_K8S4_N5.git
cd TTCS_K8S4_N5
```

Nếu cần clone ngay một nhánh của thành viên:

```powershell
git clone -b "<ten-nhanh>" https://github.com/dipthong7119/TTCS_K8S4_N5.git
```

## Cấu hình tên và email commit

```powershell
git config --global user.name "<ten-cua-ban>"
git config --global user.email "<email-cua-ban>"
```

## Chuyển nhánh và cập nhật code

Kiểm tra thay đổi trước khi chuyển nhánh:

```powershell
git status
git branch
git switch "<ten-nhanh>"
git pull --ff-only
```

Tạo nhánh mới nếu công việc chưa có nhánh:

```powershell
git switch -c "<ten-nhanh-moi>"
```

## Commit và push

Kiểm tra diff, sau đó chọn các file của công việc cần đưa lên GitHub:

```powershell
git diff
git add "<duong-dan-file-hoac-thu-muc>"
git commit -m "<mo-ta-thay-doi>"
git push -u origin "<ten-nhanh>"
```

## Vị trí tài liệu trong dự án

- Phân công: [Phan_cong_Sprint3.md](Phan_cong_Sprint3.md).
- Backlog/tasks: workbook `.xlsx` trong thư mục `huongdan/` này.
- Quy tắc và cấu trúc: [codebase map](../prompts/01_CODEBASE_MAP.md).
- Khởi chạy và kiểm thử: [README dự án](../README.md).
- Kết quả kiểm thử: thư mục `ketqua/`.
